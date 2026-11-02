# Soyuz-Pribor Test Assignment — AI Product Copywriter

CLI на Python для подготовки русскоязычных B2B-карточек из входных сведений. Работает на стандартной библиотеке Python и совместимом с OpenAI Chat Completions API. Установка сторонних Python-пакетов не требуется.

## Быстрый запуск

Требуется Python 3.10+. Клонируйте репозиторий:

```powershell
git clone https://github.com/catlsp/soyuz-pribor-test-assignment.git
cd soyuz-pribor-test-assignment
```

Из корня проекта можно сразу получить демонстрационные карточки без API-ключа:

```powershell
python -m product_copywriter examples/inputs.json --demo --format json --output examples/results.json
python -m product_copywriter examples/inputs.json --demo --format markdown --output examples/results.md
```

Для генерации через модель задайте ключ и, если нужно, endpoint и модель. `.env` приложение автоматически не загружает: переменные передаются процессу через оболочку.

```powershell
$secret = Read-Host 'API-ключ' -AsSecureString
$env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new('', $secret).Password
$env:OPENAI_BASE_URL = "https://api.openai.com/v1"
$env:OPENAI_MODEL = "gpt-4.1-mini"
$env:OPENAI_TIMEOUT = "30"
python -m product_copywriter examples/inputs.json --format json --output results.json
```

Поля `.env.example` соответствуют этим переменным. Не сохраняйте настоящий ключ в файле проекта или репозитории: `.env` и `.env.*` исключены через `.gitignore`, шаблон `.env.example` разрешён. Для проверенного провайдера CheapVibeCode задайте `OPENAI_BASE_URL=https://cheapvibecode.ru/v1`, `OPENAI_MODEL=gpt-6-luna`, `OPENAI_TIMEOUT=120`.

Для проверки другого файла замените `examples/inputs.json` на путь к своему JSON. CLI принимает один объект либо массив товаров. Формат Markdown можно получить параметром `--format markdown`; `--output` задаёт файл результата.

## Входные данные

Обязательное поле только `name`. `manufacturer`, `specs` и `description` необязательны. Характеристики — объект с простыми значениями. `expected_fields` задаёт характеристики, которые надо показать в выходе; по умолчанию это `Диапазон измерений`, `Класс точности`, `Питание`, `Тип корпуса`, `Интерфейсы`.

```json
{
  "name": "Манометр технический",
  "manufacturer": "Манотомь",
  "specs": {"Диапазон измерений": "0–1,6 МПа", "Класс точности": "1,5"},
  "description": "Прибор предназначен для измерения избыточного давления.",
  "expected_fields": ["Диапазон измерений", "Класс точности"]
}
```

Если характеристика отсутствует, в структурированном списке будет `данных нет`, а имя поля попадёт в `missing_fields`. Пустые данные производителя и описания также отмечаются как пропуски. Полные входные характеристики сохраняются в структурированном результате; в текст описания могут попасть только те, что помещаются в лимит длины.

## Результат и ограничения

JSON содержит `seo_title`, `description`, `specs`, `queries`, `commercial_block`, `missing_fields` и `mode`. SEO-заголовок ограничен 70 символами, описание — 800–1200 символами, поисковых фраз — 3–5. Модель предлагает план и порядок включения подготовленных фактов; программа собирает текст из исходных значений и ограниченного набора нейтральных рекомендаций. Свободный текст модели не публикуется. Демонстрационный режим использует тот же рендерер без LLM и помечает результат `DEMO — не LLM`.

Такая схема снижает возможность добавить в текст не переданные технические факты, но не доказывает истинность сведений во входе и не проверяет их по паспорту изделия. Название товара также берётся из источника. Перед публикацией сверьте исходные данные с документацией конкретного исполнения.

В `examples/inputs.json` первый товар основан на фрагменте задания о манометре DM 02. Полные исходные данные второго назначенного товара отсутствуют, поэтому второй пример — явно помеченный синтетический неполный ввод, а не фактический товар из задания.

## Примеры и проверка

Актуальная версия проверена реальным вызовом через CheapVibeCode с моделью `gpt-6-luna`. Результаты без ручной редакторской правки: [JSON](examples/results.llm.checked.json) и [Markdown](examples/results.llm.checked.md). Описания содержат 838 и 851 символ, заголовки — 44 и 68, поисковых фраз — по четыре. Проверено, что весь текст входит в разрешённый каталог для соответствующего товара; см. [отчёт о проверках](docs/live-check.md).

`examples/results.json` и `examples/results.md` — актуальный демонстрационный вывод без API. `examples/results.llm.raw.json`, `examples/results.llm.json` и `examples/results.llm.md` — архив прежнего свободнотекстового прогона: необработанный ответ модели и варианты после ручной правки. Для оценки текущей версии используйте файлы `results.llm.checked.*`.

Для локальных автоматических проверок:

```powershell
python -m unittest discover -s tests -v
```

Решения, ограничения и улучшения описаны в [docs/decisions.md](docs/decisions.md); сверка задания — в [docs/requirements-checklist.md](docs/requirements-checklist.md); черновик сопроводительного письма — в [docs/submission.md](docs/submission.md).
