"""Render an LLM editorial plan using source facts and approved neutral advice.

No free-form model text is accepted by this module. Source data may be incorrect;
grounding establishes provenance, not the truth of a supplied product passport.
"""
from __future__ import annotations

from .models import deterministic_specs, validate_output

ADVICE = {
    "requirements": "Перед закупкой сопоставьте предоставленные характеристики с требованиями к приобретаемому прибору.",
    "missing": "Если необходимого параметра нет в исходных данных, запросите его у поставщика до принятия решения.",
    "version": "Проверьте, что описание и характеристики относятся к тому исполнению товара, которое вы планируете заказать.",
    "comparison": "Для сравнения предложений используйте подтверждённые сведения, а неизвестные значения уточняйте отдельно.",
    "documentation": "Карточка является черновиком и не заменяет техническую документацию производителя на конкретное изделие.",
    "request": "В запросе поставщику перечислите обязательные требования и попросите подтвердить каждый нужный параметр.",
    "conditions": "Условия эксплуатации и совместимость с оборудованием проверяйте по документации, если они важны для вашей задачи.",
    "delivery": "Комплектность и условия поставки уточняйте отдельно; отсутствие этих сведений не означает их подтверждения.",
    "purpose": "Сначала определите задачу измерения, затем проверьте соответствие выбранного прибора требованиям к этой задаче.",
    "review": "Перед публикацией сверьте исходные сведения и формулировки карточки с актуальными материалами поставщика.",
}


def _text(value: str) -> str:
    return " ".join(value.split())


def _short_name(name: str) -> str:
    text = _text(name)
    if len(text) <= 70:
        return text
    # Never split a technical value or model identifier to fit a title.
    words = text.split()
    selected = []
    for word in words:
        if len(" ".join([*selected, word])) > 70:
            break
        selected.append(word)
    return " ".join(selected) or "Прибор: исходные сведения и подбор"


def build_catalog(product: dict) -> dict:
    """Build bounded candidates; full source specs always remain in output rows."""
    full_name = _text(product["name"])
    name = _short_name(full_name)
    titles = [name]
    maker = _text(product["manufacturer"])
    for title in (f"{name} — характеристики", f"{name} — подбор", f"{name} {maker}"):
        if title not in titles and len(title) <= 70:
            titles.append(title)
    facts = {}

    def add(identifier, sentence, limit=320):
        if len(sentence) <= limit:
            facts[identifier] = sentence

    add("name", f"Наименование по исходным данным: «{_text(product['name'])}».")
    if "name" not in facts:
        facts["name"] = "Полное наименование передано во входных данных; перед заказом сверьте обозначение прибора с документацией."
    if maker:
        add("manufacturer", f"Производитель по исходным данным: «{maker}».")
    else:
        facts["manufacturer"] = "Производитель: данных нет; уточните его перед закупкой."
    description = _text(product["description"])
    if description:
        add("description", f"Сведения из исходного описания: «{description}».", 440)
    else:
        facts["description"] = "Описание назначения и задач применения: данных нет."
    rows, missing = deterministic_specs(product)
    for index, row in enumerate(rows[:12]):
        add(f"spec_{index}", f"В исходных характеристиках: {_text(row['name'])} — {_text(row['value'])}.", 180)
    queries = [full_name, f"купить {full_name}", f"{full_name} характеристики", f"{full_name} подбор", f"{full_name} поставщик"]
    purpose = (
        f"Задача по исходному описанию: «{description}»."
        if description and len(description) <= 300 else
        "Задачи применения: данных нет в кратком подтверждённом виде; уточните назначение по исходной документации."
    )
    # These describe the purchase process, not an unsupported industry/application.
    commercial = {
        "selection": "Для специалиста, который подбирает прибор под требования закупки. " + purpose,
        "comparison": "Для специалиста, который сравнивает приборы перед закупкой. " + purpose,
    }
    return {
        "facts": facts,
        "advice": dict(ADVICE),
        "titles": {f"title_{i}": value for i, value in enumerate(titles)},
        "queries": {f"query_{i}": value for i, value in enumerate(queries)},
        "commercial": commercial,
    }


def default_plan(catalog: dict) -> dict:
    return {
        "fact_order": list(catalog["facts"]),
        "advice_order": list(catalog["advice"]),
        "title_id": next(iter(catalog["titles"])),
        "query_ids": list(catalog["queries"])[:4],
        "commercial_id": "selection",
    }


def _ids(value, allowed, field, *, minimum=1, maximum=None):
    if (not isinstance(value, list) or not minimum <= len(value) <= (maximum or len(allowed))
            or not all(isinstance(item, str) and item in allowed for item in value)
            or len(value) != len(set(value))):
        raise ValueError(f"Поле плана {field} должно содержать уникальные ID из предоставленного каталога.")
    return value


def render_plan(plan: dict, product: dict, *, demo=False) -> dict:
    catalog = build_catalog(product)
    required = {"fact_order", "advice_order", "title_id", "query_ids", "commercial_id"}
    if not isinstance(plan, dict) or set(plan) != required:
        raise ValueError("Модель должна вернуть редакторский план с требуемыми ID, без свободного текста.")
    facts = _ids(plan["fact_order"], catalog["facts"], "fact_order")
    if set(facts) != set(catalog["facts"]):
        raise ValueError("fact_order должен перечислять все ID исходных фактов ровно один раз.")
    advice = _ids(plan["advice_order"], catalog["advice"], "advice_order")
    queries = _ids(plan["query_ids"], catalog["queries"], "query_ids", minimum=3, maximum=5)
    for field, candidates in (("title_id", "titles"), ("commercial_id", "commercial")):
        if not isinstance(plan[field], str) or plan[field] not in catalog[candidates]:
            raise ValueError(f"Поле плана {field} должно быть ID из каталога.")
    sentences = []
    length = 0
    for identifier in facts:
        sentence = catalog["facts"][identifier]
        if length + len(sentence) + bool(sentences) <= 950:
            sentences.append(sentence)
            length = len(" ".join(sentences))
    # The model prioritizes the advice. Remaining approved clauses fill short inputs.
    advice = [*advice, *(identifier for identifier in ADVICE if identifier not in advice)]
    for identifier in advice:
        if length >= 800:
            break
        sentence = ADVICE[identifier]
        if length + len(sentence) + bool(sentences) <= 1200:
            sentences.append(sentence)
            length = len(" ".join(sentences))
    if not 800 <= length <= 1200:
        raise ValueError("Недостаточно подходящих исходных фрагментов для описания нужной длины.")
    result = validate_output({
        "seo_title": catalog["titles"][plan["title_id"]],
        "description": " ".join(sentences),
        "queries": [catalog["queries"][identifier] for identifier in queries],
        "commercial_block": catalog["commercial"][plan["commercial_id"]],
    }, product)
    result["mode"] = "DEMO — не LLM" if demo else "LLM"
    return result
