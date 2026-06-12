# Baseline Pipeline ve MCMC Akışı

Bu dosya, `baseline_pipeline.py` içindeki üretim ve arama mantığını açıklar.

## Mode Yapısı

Sistem şu an iki mode ile çalışır:
- `door_only`
- `stamina_only`

Mode bilgisi `ModeConfig` ile tutulur.

Her mode şu alanları belirler:
- stamina solver kullanılsın mı
- başlangıç stamina değeri
- kapı kilitli mi
- başlangıçta hangi item’lar var
- proposal hamle tipleri

`stamina_only` modda `initial_stamina = None` ise stamina elle verilmez; grid boyutu ve hedef difficulty üzerinden otomatik hesaplanır. Bu değer initial state oluşturulurken bir kez seçilir ve MCMC state proposal'ları arasında değişmez.

Otomatik initial stamina formülü:

```text
grid_scale =
  sqrt(GRID_WIDTH * GRID_HEIGHT)

mean_initial_stamina =
  grid_scale
  * (
      INITIAL_STAMINA_BASE_SCALE
      + INITIAL_STAMINA_DIFFICULTY_SCALE * TARGET_AGENT_DIFFICULTY
    )

std_initial_stamina =
  grid_scale * INITIAL_STAMINA_NOISE_STD_SCALE

sampled_initial_stamina =
  Normal(mean_initial_stamina, std_initial_stamina)

initial_stamina =
  round(
    clamp(
      sampled_initial_stamina,
      grid_scale * MIN_INITIAL_STAMINA_SCALE,
      grid_scale * MAX_INITIAL_STAMINA_SCALE
    )
  )
```

Bu random sapma global seed'e bağlıdır. Yani aynı seed ile aynı initial stamina seçilir. Difficulty arttıkça ortalama initial stamina artar; amaç yüksek difficulty'de sadece stamina kıtlığı değil, daha uzun ve karmaşık rotalara alan açmaktır.

## Başlangıç State Üretimi

### `door_only`

Bu modda başlangıç state daha klasik şekilde üretilir:
- maze üretilir
- door seçilir
- item yoksa doğrudan geçerlilik kontrol edilir

### `stamina_only`

Bu modda tamamen rastgele başlangıç state üretmek çoğu zaman zordu.

Sebep:
- düşük veya orta stamina ile
- tamamen rastgele item ve door konumları
- HC3’ü çok sık bozuyordu

Bu yüzden constructive ve energy-aware bir seed üretimi kullanılır.

Güncel akış:
1. maze üretilir
2. otomatik veya config kaynaklı `initial_stamina` hesaplanır
3. stamina bütçesi, target difficulty, spacing hedefi ve stamina usage hedefi ile birden fazla door adayı üretilir
4. door adayları sadece tek hedef mesafeden seçilmez; yakın, hedefe yakın ve uzak adaylar birlikte denenir
5. her door adayı için `start -> door` shortest path bulunur
6. her path için birden fazla item placement stratejisi denenir
7. her candidate HC1/HC2/HC3 ile doğrulanır
8. valid candidate’ların energy değeri hesaplanır
9. `INITIAL_VALID_CANDIDATE_LIMIT` kadar valid candidate içinden en düşük energy’li state seçilir
10. candidate energy `INITIAL_EARLY_STOP_ENERGY` altına inerse arama erken biter

Item placement stratejileri:
- tüm stamina/key item’larını path üzerinde dengeli dağıtma
- `TARGET_STAMINA_USAGE_RATE` veya `TARGET_AGENT_DIFFICULTY` kadar stamina item’ı ana route üstüne koyup kalanları off-path yayma
- eski progressive path placement fallback’i
- sınırlı sayıda randomized path/off-path placement

Item placement adayları ayrıca start'a çok yakın olmamaları için filtrelenir. Minimum uzaklık grid boyutundan türetilir:

```text
min_item_start_distance =
  max(2, round(sqrt(GRID_WIDTH * GRID_HEIGHT) * INITIAL_ITEM_MIN_START_DISTANCE_SCALE))
```

Bu uzaklık BFS shortest-path mesafesidir, Manhattan değildir. Eğer bir maze/path bu şartla hiç candidate üretemezse generator sırasıyla daha gevşek fallback eşiklerine düşer. Böylece item'ların start'a yapışması engellenir ama initial state üretimi tamamen kilitlenmez.

Bu tasarım initial state’i tek bir hard-coded çözüm rotasına kilitlemez. Energy fonksiyonu hangi aday hedeflere daha uygunsa onu seçer. Energy fonksiyonu ileride değişirse initial state generator da otomatik olarak yeni hedeflere daha uyumlu state seçmeye başlar.

## Proposal Hamleleri

Şu an desteklenen hamleler:

### `topology`
- bir yol hücresini duvar yapmak
- ya da bir duvar hücresini yol yapmak

Ama:
- HC1/HC2/HC3 bozulmamalı
- start, door ve item hücreleri korunmalı

### `item_move`
- bir item başka bir walkable hücreye taşınır

Kurallar:
- start ile çakışmaz
- door ile çakışmaz
- diğer item’larla çakışmaz

### `door_move`
- door başka bir walkable hücreye taşınır

Kurallar:
- start ile çakışmaz
- item ile çakışmaz

## Önemli Tasarım Kararı

`locked_door` artık proposal değildir.

Yani:
- kapının kilitli olup olmaması MCMC adımıyla değişmez
- bu bilgi başlangıçtan sabit gelir

Bu karar kullanıcı tercihine göre alınmıştır.

## Hamle Tipi Seçimi

Hamle tipleri şu an uniform seçilir:
- `random.choice(mode_config.proposal_move_types)`

Yani bir mode içindeki tüm hamle tiplerinin olasılığı şu an eşittir.

Örnek:
- `stamina_only` modda `topology`, `item_move`, `door_move` yaklaşık eşit sıklıkta denenir

## Candidate Kabul Mantığı

Her MCMC adımında:
1. bir candidate önerilir
2. geçersiz lokal hamle ise sayılır ama kullanılmaz
3. candidate geçerliyse energy hesaplanır
4. Metropolis-Hastings kuralı ile kabul veya red verilir

Kural:
- candidate energy daha iyiyse doğrudan kabul
- daha kötüyse sıcaklığa bağlı olasılıkla kabul

Bu sayede zincir sadece greedy davranmaz.

## Best State Takibi

Algoritma iki state taşır:
- `current_state`
- `best_state`

`current_state`
- zincirin o andaki state’i

`best_state`
- tüm çalışma boyunca görülen en düşük energy’li state

Bu ayrım önemlidir çünkü final state her zaman best state olmak zorunda değildir.

## Terminal Çıktısı

Pipeline şu bilgileri yazar:
- initial state ASCII görünümü
- initial energy
- energy breakdown
- solution summary
- periyodik step log’ları
- final state özeti
- best state özeti

`viz_maze.py` kullanıldığında da artık final ve best summary ayrıca terminale yazdırılır.
