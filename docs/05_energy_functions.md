# Energy Fonksiyonlari

Bu dosya, projedeki energy fonksiyonlarinin neyi olctugunu aciklar.

Daha matematiksel ve detayli formuller icin:
- [latex/energy_functions.tex](latex/energy_functions.tex)

## Neden Energy Var

MCMC zincirinin bir candidate state'i iyi ya da kotu olarak degerlendirebilmesi icin sayisal bir hedef gerekir.

Bu hedefe energy diyoruz.

Genel kural:
- energy ne kadar dusukse state o kadar iyi

## 1. `door_only` Energy

Bu eski baseline energy'dir.

Formul:

```text
E = |L - L_target|
```

Burada:
- `L`: `start -> door` en kisa yol uzunlugu
- `L_target`: hedef path uzunlugu

Ozellikler:
- sadece geometrik kisa yol uzunluguna bakar
- item, stamina, key gibi semantik bilgi yoktur

Bu yuzden sadece `door_only` mod icin uygundur.

## 2. `stamina_only` Baseline Energy

Bu energy, `stamina_only` HC3 analizini kullanir.

Formul:

```text
E = w_path * |P - P_target| + w_stamina * |S - S_target|
```

Burada:
- `P`: gecerli basarili cozum yollari icindeki en kisa basarili cozum maliyeti
- `P_target`: hedef cozum uzunlugu
- `S`: basarili cozumde kapiya varinca elde kalan en iyi stamina
- `S_target`: hedef final stamina
- `w_path`: path agirligi
- `w_stamina`: stamina agirligi

Varsayilanlar:
- `w_path = 1.0`
- `w_stamina = 1.0`

## `P` Nasil Hesaplaniyor

Solver basarili bir senaryo buldugunda:

```text
success_path_length = initial_stamina + collected_stamina - remaining_stamina
```

Bu deger oyuncunun toplam harcadigi hareket maliyetini temsil eder.

Sebep:
- baslangicta belli bir stamina ile basliyoruz
- yolda stamina item'lari topluyoruz
- sonunda bir miktar stamina kaliyor

Dolayisiyla:
- elde edilen toplam stamina kaynagi
- eksi finalde kalan stamina
- bize yuruyus maliyetini verir

## `S` Nasil Hesaplaniyor

Basarili cozumler arasinda:
- kapiya varildiginda elde kalan en yuksek stamina

secilir.

Bu deger, haritanin oyuncuya ne kadar rahat bir cozum sundugunu olcmeye yarar.

## Cozulemez Haritalar

Eger solver haritanin cozulemez oldugunu soylerse:
- energy = `infinity`

olur.

Bu sayede MCMC boyle state'leri tercih etmez.

## Energy Breakdown

Kodda sadece toplam energy degil, terimlere ayrilmis hali de uretilir.

`baseline` stamina modelinde terminal ciktisinda su alanlar gorulur:
- `target_path`
- `path`
- `path_term`
- `target_final_stamina`
- `final_stamina`
- `stamina_term`
- `total`

## 3. Agent Difficulty Energy

Detayli ajan davranisi ve sample propagation aciklamasi icin:
- [08_agent_difficulty_model.md](08_agent_difficulty_model.md)

Yeni agent difficulty energy ajan tabanli zorluk terimlerini kullanir. Bu modelde eski `TARGET_PATH_LENGTH` kullanilmaz. Baseline'daki sabit `TARGET_FINAL_STAMINA` da kullanilmaz; onun yerine `TARGET_AGENT_DIFFICULTY` degerinden turetilen dinamik bir final stamina hedefi kullanilir.

Kisa notasyon:
- `D_target`: `TARGET_AGENT_DIFFICULTY`, 0 ile 1 arasinda hedef zorluk
- `D_main`: exact cozulebilen route'larin agent zorlugu
- `IS`: initial stamina
- `F`: `FINAL_STAMINA_TARGET_FACTOR`
- `R_i`: exact cozulebilen plan `i` icin agent estimated success rate
- `S_i`: exact cozulebilen plan `i` icin basarili ajanlarin ortalama final stamina degeri
- `std_segments`: unique simule edilmis segment success rate'lerinin standart sapmasi
- `dead_ratio`: unique dead segment orani

Toplam enerji:

```text
E_total =
  E_difficulty
  + E_segment_balance
  + E_dead_segment
  + E_final_stamina
  + E_spacing
```

Difficulty terimi:

```text
main_route_success_rate =
  average(R_i for exact-solvable plans)

D_main =
  1 - main_route_success_rate

E_difficulty =
  AGENT_DIFFICULTY_WEIGHT
  * abs(D_main - D_target)
```

Segment denge terimi:

```text
segment_balance_score =
  min(1, 2 * std_segments)

E_segment_balance =
  SEGMENT_BALANCE_WEIGHT
  * segment_balance_score
```

Dead segment terimi:

```text
dead_ratio =
  dead_unique_segments / all_unique_segments

E_dead_segment =
  DEAD_SEGMENT_WEIGHT
  * dead_ratio
```

Final stamina terimi:

```text
target_final_stamina =
  F * IS * (1 - D_target)

weighted_final_stamina =
  sum(R_i * S_i) / sum(R_i)

final_stamina_score =
  min(
    1,
    abs(target_final_stamina - weighted_final_stamina)
    / max(1, IS)
  )

E_final_stamina =
  FINAL_STAMINA_WEIGHT
  * final_stamina_score
```

Bu ters oranti bilincli:
- `D_target` yuksekse hedef final stamina dusuk olur
- `D_target` dusukse hedef final stamina yuksek olur

Spacing terimi:

```text
spacing_actual =
  average(
    shortest_path(start, key),
    shortest_path(key, door),
    shortest_path(start, door)
  )

grid_scale =
  sqrt(grid_width * grid_height)

spacing_target =
  SPACING_TARGET_SCALE
  * grid_scale
  * (0.5 + 0.5 * D_target)

spacing_score =
  min(
    1,
    abs(spacing_target - spacing_actual)
    / (2 * SPACING_TARGET_SCALE * grid_scale)
  )

E_spacing =
  SPACING_WEIGHT
  * spacing_score
```

`baseline_pipeline.py` icindeki ilgili parametreler:
- `TARGET_AGENT_DIFFICULTY`
- `AGENT_DIFFICULTY_WEIGHT`
- `SEGMENT_BALANCE_WEIGHT`
- `DEAD_SEGMENT_WEIGHT`
- `FINAL_STAMINA_WEIGHT`
- `FINAL_STAMINA_TARGET_FACTOR`
- `SPACING_WEIGHT`
- `SPACING_TARGET_SCALE`
- `AGENTS_PER_SEGMENT`
- `AGENT_DIFFICULTY_SEED`

## Agent Difficulty Nasil Hesaplaniyor

Once HC3 semantic graph uzerinden door'a giden tum simple semantic planlar cikarilir.

Ornek planlar:
- `start -> door`
- `start -> item:key -> door`
- `start -> item:stamina -> item:key -> door`

Exact olarak cozulemeyen planlar da listede kalir. Bu planlar main route difficulty ortalamasina katilmaz; bunun yerine dead segment hesabina katki verir.

Exact olarak cozulebilen planlarda her plan segmenti icin ajanlar calistirilir.

Ornek segmentler:
- `start -> item:key`
- `item:key -> item:stamina`
- `item:stamina -> door`

Her segmentte ajanlar:
- hedef node'a ulasmaya calisir
- henuz toplanmamis diger item node'larini duvar gibi gorur
- daha once toplanmis item node'larini yol gibi gecilebilir kabul eder
- mumkunse daha once basmadigi hucreleri secer
- seceneklerin hepsi ziyaret edildiyse geriye donmek yerine baska ziyaret edilmis secenekleri dener
- sadece cikmaz sokakta mecburen geri doner
- stamina biterse basarisiz olur

Her segment icin tutulan metrikler:
- success rate
- kalan stamina ornekleri
- ortalama adim sayisi
- ortalama revisit sayisi
- ortalama forced backtrack sayisi

Bir segment basarili oldugunda, hedef node stamina item ise kalan stamina'ya item degeri eklenir. Bu ornekler sonraki segmentin baslangic stamina dagilimi olarak kullanilir.

Plan basari orani, segment basari oranlarinin carpimidir.

Main route seviyesinde:

```text
D_main_route = 1 - average_success_rate_of_exact_solvable_routes
```

Yani exact cozulebilen route'larin ortalama gecilme orani dusukse ana route zorlugu yuksek kabul edilir.

Ek olarak unique segmentler uzerinden iki kalite cezasi hesaplanir:

```text
segment_success_std = std(unique attempted segment success rates)
segment_balance_score = min(1, 2 * segment_success_std)
dead_segment_ratio = dead_unique_segments / all_unique_segments
```

Bu ayrim sunu engeller:
- tek segment cok kolay, diger segment cok zor olunca toplam route success hedefe denk gelse bile `segment_success_std` ceza verir
- cok fazla exact dead semantic baglanti varsa, ana route kolay olsa bile `dead_segment_ratio` ceza verir

`segment_success_std` hesabina agent success rate `0` olan exact-gecilebilir segmentler de dahildir. `all_unique_segments`, route suffix'lerini sisme olacak sekilde saymaz. Sadece ajan tarafindan gercekten simule edilen segmentler ve exact dead planlarda ilk basarisiz semantic segment dahil edilir.

Final stamina terimi exact solvable planlarin basarili agent sonuclarindan hesaplanir:

```text
target_final_stamina =
  FINAL_STAMINA_TARGET_FACTOR
  * initial_stamina
  * (1 - TARGET_AGENT_DIFFICULTY)

weighted_final_stamina =
  sum(plan_success_rate * avg_final_stamina_for_plan)
  / sum(plan_success_rate)

final_stamina_score =
  min(
    1,
    abs(target_final_stamina - weighted_final_stamina)
    / max(1, initial_stamina)
  )
```

Bu normalizasyon final stamina terimini initial stamina scale'ine getirir. Burada `(1 - TARGET_AGENT_DIFFICULTY)` kullanilir; hedef zorluk arttikca beklenen final stamina azalir.

Spacing terimi start, key ve door'un grid uzerindeki en kisa yol uzakliklarini kullanir:

```text
spacing_actual =
  average(
    shortest_path(start, key),
    shortest_path(key, door),
    shortest_path(start, door)
  )

grid_scale = sqrt(grid_width * grid_height)
spacing_target =
  SPACING_TARGET_SCALE
  * grid_scale
  * (0.5 + 0.5 * TARGET_AGENT_DIFFICULTY)

spacing_score =
  min(
    1,
    abs(spacing_target - spacing_actual)
    / (2 * SPACING_TARGET_SCALE * grid_scale)
  )
```

Key yoksa sadece `start -> door` uzakligi kullanilir. `spacing_actual` ve `spacing_target` terminalde ham path uzunlugu olarak gorunur; enerjiye giren normalize edilmis deger `spacing_score` alanidir. Bu terim ozellikle start-key-door uclusunun birbirine yapismasini cezalandirmak icindir.

## Deterministic Randomness

Ajanlar stochastic davranir ama ayni state ayni energy degerini uretmelidir.

Bu yuzden ajan simulasyonlarinda kullanilan random seed:
- global agent seed
- plan node sirasi
- segment source/target bilgisi

uzerinden deterministik uretilir.

Bu sayede ayni harita tekrar degerlendirildiginde ayni agent difficulty sonucu alinir.
