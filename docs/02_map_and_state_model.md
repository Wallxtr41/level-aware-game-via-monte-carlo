# Map ve State Modeli

Bu dosya, haritanin ve MCMC/solver tarafinda kullanilan state yapilarinin neyi temsil ettigini aciklar.

## Grid Temsili

Harita 2D grid olarak tutulur.

Hucre kodlari:
- `0`: yol / walkable cell
- `1`: duvar / blocked cell

Grid su islemlerde kullanilir:
- connectivity analizleri
- shortest path hesaplari
- HC1/HC2/HC3 kontrolleri
- gorsellestirme

## Temel Konumlar

Her state icinde en az sunlar vardir:
- `start`
- `door`

`stamina_only` modda ek olarak:
- `key`
- `stamina` itemlari

## Item Modeli

Item'lar `utils/map_entities.py` icindeki `ItemPlacement` ile temsil edilir.

Alanlar:
- `kind`
- `position`
- `value`

Ornek kind'lar:
- `stamina`
- `key`
- `power`

`power` genel entity modelinde vardir ama mevcut stamina-only baseline'da kullanilmaz.

## BaselineState

`baseline_pipeline.py` icinde MCMC'nin calistigi ana state:
- `grid`
- `start`
- `door`
- `items`
- `initial_stamina`
- `locked_door`

Bu container hem `door_only` hem `stamina_only` modu icin kullanilir.

## `door_only` Yorumu

Bu modda:
- `items` bostur
- `initial_stamina = 0`
- `locked_door = False`

Anlamli parcalar:
- grid
- start
- door

## `stamina_only` Yorumu

Bu modda:
- `initial_stamina`, oyuncunun baslangic stamina butcesidir
- `items`, key ve stamina itemlarini tasir
- `locked_door`, kapinin baslangicta kilitli olup olmadigini soyler

`initial_stamina` MCMC proposal'lari sirasinda degismez. `initial_stamina = None` ise deger initial state uretiminde grid boyutu, `TARGET_AGENT_DIFFICULTY` ve seed'e bagli normal sapma ile otomatik hesaplanir.

`locked_door` proposal hamlesiyle degismez; config seviyesinde belirlenir.

## Kapi Semantigi

Guncel karar:
- kapali kapi duvar gibi bloklanir
- kapali kapi semantic target degildir
- kapali kapi transit yol degildir
- anahtar alindiktan sonra veya kapi bastan aciksa aktif target olur
- aktif kapiya ulasmak oyunu bitirir

Bu semantik su katmanlarda ayni uygulanir:
- exact HC3 solver
- semantic plan enumeration
- agent segment simulation
- spacing energy icindeki start-key-door path olcumu

## Solver State

HC3 solver icindeki state:
- `node_id`
- `remaining_stamina`
- `collected_items_mask`
- `has_key`

MCMC state haritanin kendisini temsil eder. Solver state ise o harita uzerindeki oynanis senaryosunu temsil eder.
