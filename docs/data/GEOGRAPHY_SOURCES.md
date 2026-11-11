# Geography seed data / بيانات البلدان والمدن

COUNTRY contains the 249 ISO 3166-1 alpha-2 entries (lowercase storage keys).
Arab League countries precede the remaining countries: Saudi Arabia, Gulf states,
then the other Arab states. The remainder sorts by the English display name,
ignoring accents. Existing Saudi city keys and existing country labels are retained.
CITY contains 108 named principal cities plus 249 country-specific Other entries.
These are starting lists; organizations can add cities, rename entries or deactivate them.

تتضمن القائمة 249 بلدًا وإقليمًا وفق ISO، و108 مدن رئيسية، وخيار «أخرى» لكل بلد.
الترتيب بعد البلدان العربية أبجدي بحسب الاسم الإنجليزي، مع الحفاظ على مفاتيح المدن السعودية.
التعبئة تضيف الناقص فقط ولا تعدّل تخصيصات المنظمة أو العناصر المعطلة.

Data sources (snapshot retrieved 2026-11-12; no runtime dependency):
- ISO keys: https://github.com/pycountry/pycountry/blob/main/src/pycountry/databases/iso3166-1.json
- Arabic labels: https://github.com/unicode-org/cldr-json/blob/main/cldr-json/cldr-localenames-full/main/ar/territories.json
- English labels: https://github.com/unicode-org/cldr-json/blob/main/cldr-json/cldr-localenames-full/main/en/territories.json
- Unicode data license: https://www.unicode.org/license.txt

Input SHA-256:
- `iso`: `f01b812b57fba9f31ff621bf33e7c7570a01964dbeb5be2167e94decf538c89f`
- `ar`: `b78c4a11a9ad8358048998bcda2eb49e205d5ab281f85991ed097af7b972c3d7`
- `en`: `1326fb3bcdf8b8cf63df73ea02ea7f8bf7a8362cbb60bd12bcdb53f3ad22bf04`
