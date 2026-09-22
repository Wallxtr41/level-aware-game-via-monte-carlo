# Energy Fonksiyonu Yeniden Tasarım Notları

Bu dosya, mevcut agent-difficulty energy'nin neden istenen zorlukta labirent üretemediğinin
teşhisini ve önerilen yeni enerji terimlerini içerir.

Gözlenen şikayetler:
1. Haritalar item'lar hiç kullanılmadan bitirilebiliyor.
2. Haritanın büyük kısmına hiç uğramadan oyun bitiyor.
3. Çözüm yolu çok "obvious"; tek koridor gibi, karar noktası yok.
4. Ölçülen difficulty hedefe otursa bile insan için harita kolay.

---

## 1. Kök Neden Teşhisi

### 1.1 Plan ortalaması yanlış istatistik: oyuncu ortalama oynamaz

Mevcut ana terim:

```text
main_route_success_rate = average(R_i for exact-solvable plans)
```

Oyuncu tüm planların ortalamasını oynamaz; **en kolay rotayı** oynar. Haritada bir tane
trivial `start -> key -> door` planı varsa, yanında beş tane düşük başarılı
"item toplamalı" plan olması ortalamayı düşürür ve harita "zor" görünür — ama insan
için harita o tek kolay plan kadar kolaydır. Bu tek başına hem "item kullanılmadan
bitiyor" hem "kolay oluyor" şikayetini üretir: MCMC, kalabalık ve alakasız planlar
ekleyerek ortalamayı hedefe oturtabilir, en iyi planı zorlaştırmak zorunda kalmaz.

`run_metrics.csv` bunu doğruluyor: hedef 0.7 ve 0.9 koşularında ortalama-bazlı
`measured_difficulty` 0.98+ iken `best_plan_success_rate` ayrı bir hikaye anlatıyor.

**Düzeltme:** Ortalama yerine başarı-ağırlıklı ortalama (yumuşak maksimum):

```text
R_eff = sum(R_i^2) / sum(R_i)      (exact-solvable planlar üzerinde)
D_eff = 1 - R_eff
```

`R_eff` her zaman `average <= R_eff <= max` aralığındadır; kolay planlar domine eder
(oyuncu davranışı), ama `max`'ın aksine MCMC için pürüzsüzdür (tek plan değişince
sıçramaz). Difficulty terimi artık `D_eff` üzerinden hesaplanır.

### 1.2 Hiçbir terim item'ları *zorunlu* kılmıyor

Mevcut `stamina_usage` terimi success-rate ağırlıklı **ortalama** toplama oranına bakar.
Bu iki nedenle zayıf:
- Ortalama yine plan kalabalığıyla oynanabilir (1.1 ile aynı hastalık).
- "Ortalama plan item topluyor" demek "item toplamak zorunlu" demek değildir.
  Item'sız tek bir geçerli plan varsa oyuncu onu oynar.

Oyuncunun item toplamasını garanti eden tek şey **item'sız planın exact olarak
imkansız olmasıdır** (stamina bütçesi yetmez). Bu bilgi elimizde zaten var:
`enumerate_semantic_solution_plans` tüm planları veriyor ve her planın kaç stamina
item topladığı `steps`'ten okunuyor.

**Yeni terim — Item Necessity (minimum viable usage):**

```text
min_usage = min(collected_stamina_ratio_i for exact-solvable plans)
E_necessity = W * |usage_target - min_usage|
```

`min_usage`, oyuncunun "yırtabileceği" en düşük item kullanımıdır. `min_usage = 0`
ise harita item'sız bitirilebilir demektir; hedef 0.5+ iken bu doğrudan cezalanır.
MCMC bunu düşürmenin tek yolu itemsız/az-itemli planları stamina bütçesiyle
öldürmektir → item'lar gerçekten zorunlu hale gelir. Ortalama-bazlı eski ölçüm
yerine bu min-bazlı ölçüm kullanılmalı (ikisini harmanlamak da mümkün ama min olan
asıl kaldıraçtır).

### 1.3 Kapsama (coverage) hiç ölçülmüyor

"Haritanın çoğuna uğramadan bitiyor" şikayetinin karşılığı olan hiçbir terim yok.
Spacing terimi sadece start-key-door bacak uzunluklarına bakar; harita alanının ne
kadarının oyunda "yaşadığını" ölçmez.

**Yeni terim — Coverage:**

Ajanlar zaten her segmentte `visited_positions` kümesi tutuyor; sadece sayısı dışarı
verilmiyor. Karar mantığına dokunmadan telemetri olarak `visited_count` eklenir.

```text
plan* = en yüksek R_i'li plan (oyuncunun oynayacağı rota)
expected_visited = sum over segments of plan* ( avg visited_count of successful agents )
coverage = min(1, expected_visited / walkable_cell_count)
coverage_target = C_BASE + C_SCALE * D_target
E_coverage = W * |coverage_target - coverage|
```

Kolay-obvious haritada başarılı ajanlar koridoru takip eder, `coverage` düşük çıkar
ve yüksek hedefte ceza üretir. MCMC kapsamayı artırmak için rotayı haritaya yaymak,
item'ları uzak bölgelere koymak zorunda kalır. (Segment'ler arasında hücre tekrarı
sayılabilir; `min(1, ...)` ile kırpılır, hedef kalibrasyonu bunu absorbe eder.)

### 1.4 "Obviousness" ölçülmüyor; ajan zorluğu insan zorluğunun vekili değil

Ajan rastgele-DFS + kısıtlı görüş ile yürüyor. Bu ajan için zorluk büyük ölçüde
**stamina bütçesi vs koridor uzunluğu** meselesidir. Tek koridorlu, hiç dallanmayan
ama stamina'sı sıkı bir harita ajana "zor" görünür (D hedefi tutar), insana ise
bariz görünür — yanlış karar verme şansı yoktur. MCMC şu an tam bu ucuz çözümü
bulabiliyor; "yol çok obvious" şikayetinin kök nedeni bu.

İnsan zorluğu = karar noktaları + yanıltıcı dallar. Bu yapısal olarak ölçülebilir:

**Yeni terim — Branching / Trap Depth (yapısal):**

```text
path* = plan*'ın grid üzerine açılmış çözüm yolu (BFS ile segment segment)
junction_density = |path* üzerinde yol-dışı walkable komşusu olan hücreler| / |path*|
her yol-dışı giriş için: trap_depth = o cebin BFS derinliği (path* blokken)
trap_score = min(1, avg(trap_depth) / (0.5 * grid_scale))
branching_actual = 0.5 * junction_density + 0.5 * trap_score
branching_target = B_BASE + B_SCALE * D_target
E_branching = W * |branching_target - branching_actual|
```

- `junction_density`: çözüm yolu boyunca kaç kez "yanlış yöne sapma şansı" var.
- `trap_depth`: sapılan yanlış yol ne kadar derine götürüyor (derin tuzak = pahalı hata).

Bu terim ajan simülasyonundan bağımsızdır (deterministik, ucuz BFS) ve doğrudan
"yol obvious olmasın" hedefini optimizasyona sokar. Ajan tarafında da yan etkisi
güzeldir: dallanma arttıkça ajan success düşer, yani D_eff ile doğal bir sinerjisi vardır.

### 1.5 Dead segment cezası yanıltıcı rotaları *siliyor*

`dead_segment_ratio` cezası, exact-imkansız planları azaltmaya iter. Ama
exact-imkansız bir plan, oyuncu perspektifinden bir **tuzaktır** — denenebilir
görünen ama bütçe yetmeyen rota. Yüksek zorlukta bunlardan bir miktar İSTERİZ;
hepsini cezalandırmak haritayı daha da obvious yapar. Şu an ağırlığı 0 (kapalı),
bu iyi bir ara durum. İleride ceza yerine **hedefli tuzak oranı** yapılabilir:

```text
trap_target = T_SCALE * D_target        (örn. 0.3 * D)
E_trap = W * |trap_target - dead_segment_ratio|
```

Varsayılan olarak kapalı tutulması önerilir (önce ana terimler otursun).

### 1.6 Terim çakışmaları

- `segment_target` ve `difficulty` aynı hedefin iki ölçeği: route hedefi zaten
  segment hedeflerinin çarpımı. İkisi birden yüksek ağırlıkta olunca difficulty
  sinyali bulanıyor. `segment_target` kalmalı (zorluğun tek segmente yığılmasını
  engelliyor) ama ağırlığı düşürülmeli.
- `segment_balance` (std) ile `segment_target` neredeyse aynı şeyi ölçer;
  0 ağırlıkta kalması doğru.
- `final_stamina` difficulty ile aynı yöne iter (sıkı bütçe → düşük final stamina
  → düşük success). Küçük ağırlıkla "bitişte gerilim" ayarı olarak kalabilir.

---

## 2. Önerilen Terim Seti (aktif)

| Terim | Ölçtüğü şey | Formül özeti | Ağırlık (öneri) |
|---|---|---|---|
| `E_difficulty` | Oyuncunun oynayacağı rotanın zorluğu | `abs((1 - R_eff) - D_target)`, `R_eff = ΣR²/ΣR` | 30 |
| `E_necessity` | Item'ların zorunluluğu | `abs(usage_target - min_usage)` | 15 |
| `E_coverage` | Haritanın kullanılan oranı | `abs(cov_target - coverage)` | 10 |
| `E_branching` | Yolun obvious olmaması | `abs(branch_target - branching_actual)` | 10 |
| `E_segment_target` | Zorluğun segmentlere dağılımı | mevcut formül | 8 |
| `E_final_stamina` | Bitişteki gerilim | mevcut formül | 6 |
| `E_spacing` | Kritik noktaların ayrıklığı | mevcut formül | 10 |

Hedef parametreleri:

```text
usage_target    = TARGET_STAMINA_USAGE_RATE (None ise D_target)
coverage_target = COVERAGE_TARGET_BASE + COVERAGE_TARGET_DIFFICULTY_SCALE * D_target
branch_target   = BRANCHING_TARGET_BASE + BRANCHING_TARGET_DIFFICULTY_SCALE * D_target
```

Taban/ölçek başlangıç değerleri (kalibrasyonla güncellenecek):
`COVERAGE_TARGET_BASE=0.25`, `COVERAGE_TARGET_DIFFICULTY_SCALE=0.5`,
`BRANCHING_TARGET_BASE=0.15`, `BRANCHING_TARGET_DIFFICULTY_SCALE=0.5`.

Tüm skorlar [0,1] aralığına normalize; toplam enerji ağırlıklı toplam. Ceza
tabanlı iki eski terim (`segment_balance`, `dead_segment`) 0 ağırlıkta, ileride
1.5'teki hedefli tuzak varyantı denenebilir.

## 3. Aday ama şimdilik dışarıda bırakılan terimler

- **Wander (revisit oranı):** `avg_revisits / avg_steps` zaten toplanıyor;
  davranışsal "kaybolma" ölçüsü. Branching + coverage aynı davranışı yapısal
  yönden zorladığı için terim enflasyonunu önlemek adına dışarıda. Branching
  yetersiz kalırsa ilk eklenecek aday.
- **Item detour:** `d(start,item) + d(item,door) - d(start,door)` — item'ın ana
  rotadan sapma maliyeti. Necessity + coverage pratikte item'ları uzaklaştırdığı
  için şimdilik gereksiz.
- **Hedefli tuzak oranı:** 1.5'te anlatıldı; varsayılan kapalı.
- **Stamina slack:** `initial_stamina - min_cost` oranı; final_stamina ile büyük
  ölçüde çakışıyor.

## 4. Ajan Mantığı Değerlendirmesi (değişiklik yok)

Mevcut ajan: 4-komşu, görüş yarıçapında hedefi görürse kilitlenir, yoksa
ziyaret edilmemiş komşuyu rastgele seçer, mecbur kalırsa geri döner; toplanmamış
item'lar duvar; stamina bitince ölür.

Makul yanları:
- Segment bazlı + sample propagation kurgusu ölçeklenebilir ve deterministik;
  route success çarpımı olasılıksal olarak tutarlı.
- "Ziyaret edilmemişi tercih et" gerçek labirent oyuncusunun baskın stratejisidir.

Bilinen sapmalar (energy tarafında telafi edilen):
- Ajan yön duygusu taşımaz (kapının genel yönünü bilmez) → açık alanlarda insandan
  kötü, tek koridorda insandan iyi performans farkı yok; bu yüzden "ajan zorluğu"
  tek başına insan zorluğunu temsil edemez. Branching/coverage terimleri bu boşluğu
  yapısal olarak kapatır.
- Toplanmamış item'ın duvar sayılması gerçek oyundan sapar (oyunda üstüne basınca
  toplanır). Bu, "yolda kazara item toplama" senaryolarını plan uzayından çıkarır.
  Enumeration item'a basmayı ayrı bir plan adımı olarak zaten ürettiği için pratik
  etkisi küçük; şimdilik dokunulmuyor.
- `AGENTS_PER_SEGMENT=30` ile success rate çözünürlüğü ~0.033; D hedefine ince
  oturmak için 50-60'a çıkarmak ucuz bir iyileştirme (mantık değişikliği değil).

Koda yapılan tek dokunuş **telemetri**: `SegmentAgentResult`'a `visited_count`
alanı (ajanın gezdiği tekil hücre sayısı). Karar mantığı, seed akışı ve mevcut
metrikler birebir aynı kalır.

## 5. Kalibrasyon Protokolü

1. `D_target ∈ {0.2, 0.5, 0.8}` için kısa MCMC koşuları (100-200 adım).
2. Her koşuda logla: `D_eff`, `min_usage`, `coverage`, `branching_actual`,
   terim bazlı enerji dağılımı.
3. Bir terim toplamı domine ediyorsa (payı > %50) ağırlığını düşür; bir terim
   hep 0'a yapışıyorsa hedef taban/ölçeğini ölçülen aralığa çek.
4. Son doğrulama: `play_maze.py` ile üretilen haritayı elle oyna — item'sız
   bitirilebiliyor mu, yol tek koridor mu, haritanın ne kadarı ölü bölge.
