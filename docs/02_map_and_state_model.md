# Map ve State Modeli

Bu dosya, projede haritanın ve algoritmanın üzerinde çalıştığı state yapısının ne olduğunu açıklar.

## Grid Temsili

Harita 2D grid olarak tutulur.

Kullanılan temel hücre kodları:
- `0`: yol / walkable cell
- `1`: duvar / blocked cell

Bu grid:
- connectivity analizlerinde
- shortest path hesaplarında
- HC1/HC2/HC3 kontrollerinde
- görselleştirmede

kullanılır.

## Temel Konumlar

Her state içinde en az şu konumlar vardır:
- `start`
- `door`

`stamina_only` modda ayrıca:
- `key`
- `stamina` item’ları

vardır.

## Item Modeli

Item’lar `utils/map_entities.py` içindeki `ItemPlacement` ile temsil edilir.

Alanları:
- `kind`
- `position`
- `value`

Şu an varsayılan item değerleri:
- `stamina -> 6`
- `key -> 0`
- `power -> 3`

Not:
- `power` şu an `stamina_only` baseline’da kullanılmıyor
- ama genel entity modeli içinde tanımlı

## BaselineState

`baseline_pipeline.py` içinde MCMC’nin çalıştığı ana state:

- `grid`
- `start`
- `door`
- `items`
- `initial_stamina`
- `locked_door`

Bu state, hem `door_only` hem `stamina_only` modu için ortak container olarak kullanılır.

## `door_only` Modda State Yorumu

Bu modda:
- `items` boş olabilir
- `initial_stamina = 0`
- `locked_door = False`

Dolayısıyla asıl anlamlı parçalar:
- grid
- start
- door

olur.

## `stamina_only` Modda State Yorumu

Bu modda state şu semantiğe sahiptir:

- `initial_stamina`: oyuncunun başlangıçtaki stamina bütçesi
- `items`: key ve stamina item’ları
- `locked_door`: kapının başlangıçta kilitli olup olmadığını söyler

Burada önemli tasarım kararı şudur:
- `locked_door` proposal sırasında değişmez
- bu değer başta config ile verilir

## Semantic State ve Solver State Ayrımı

Kodda iki farklı “state” seviyesi vardır.

### 1. MCMC state
Bu, `BaselineState`’tir. Haritanın tamamını temsil eder.

### 2. Solver state
Bu, HC3 solver içinde kullanılan daha küçük arama state’idir.

`stamina_only` solver için bu state:
- `node_id`
- `remaining_stamina`
- `collected_items_mask`
- `has_key`

şeklindedir.

Yani:
- MCMC state haritanın kendisini tutar
- solver state ise bir aday harita üzerindeki oynanış senaryosunu tutar

## Kapı Semantiği

Bu projede kapı semantiği klasik “kilitli kapı = duvar” değildir.

Şu anki kesin karar:
- kapalı kapı üstünden geçilebilir
- yani transit amaçlı normal yol gibi davranır
- ama başarı üretmez
- kapı ancak aktif olduğunda hedef haline gelir

Kapı aktif olma koşulu:
- kapı baştan açık olabilir
- ya da anahtar alınmış olabilir

Bu karar özellikle HC3 solver ve solution overlay tarafını doğrudan etkiler.

