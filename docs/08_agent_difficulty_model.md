# Agent Difficulty Model

Bu dosya, stamina-only model icin eklenen ajan tabanli difficulty katmanini detayli aciklar.

Ilgili kod:
- [utils/agent_difficulty.py](../utils/agent_difficulty.py)
- [utils/energy_functions.py](../utils/energy_functions.py)
- [baseline_pipeline.py](../baseline_pipeline.py)

## Amac

HC3 solver bize sunlari soyler:
- Bu haritada en az bir gecerli cozum var mi?
- En iyi cozum ne kadar stamina harciyor?
- Kapiya varinca ne kadar stamina kaliyor?

Bu bilgiler solvability icin yeterlidir, ama pratik zorlugu tek basina anlatmaz. Iki harita da cozulebilir olabilir; birinde dogru yol cok acik, digerinde dogru yol cok dallanmis ve geri donuslu olabilir.

Agent difficulty katmani bu farki olcmek icin eklendi.

## Genel Fikir

Sistem iki seviyeli calisir:
- Semantic seviyede exact cozum planlari cikarilir.
- Her semantic segmentte ajanlar grid ustunde yurutulur.

Semantic plan ornekleri:

```text
start -> door
start -> item:key -> door
start -> item:stamina -> item:key -> door
```

Segment ornekleri:

```text
start -> item:key
item:key -> item:stamina
item:stamina -> door
```

Ajanlar tum oyunu tek parca halinde oynamaz. Ajanlar sadece iki semantic node arasindaki segmentte calisir.

## Neden Segment Bazli

HC3 semantic graph, hangi node siralamalarinin denenebilir oldugunu verir. Bu sistemde door'a giden tum simple semantic planlar listelenir. Exact olarak cozulemeyen planlar da listede kalir, ama ajan calistirilmadan success rate `0` kabul edilir.

Segment bazli yaklasim:
- daha ucuzdur
- daha aciklanabilirdir
- hangi bolgenin zor oldugunu segment metrikleriyle gosterir

## Semantic Plan Cikarma

Fonksiyon:

```python
enumerate_semantic_solution_plans(...)
```

Bu fonksiyon HC3 graph ustunde DFS yaparak door'a giden tum simple semantic planlari cikarir.

Solver state su bilgileri tasir:
- bulundugu semantic node
- kalan stamina
- toplanmis item maskesi
- key alindi mi

Bir plan door'a ulasan semantic siralama ise listeye eklenir. Planin exact olarak basarili olup olmadigi ayrica `semantic_success` alaninda tutulur.

Plan icinde ayni non-door semantic node tekrar ziyaret edilmez. Bu, semantic seviyede gereksiz cycle olusmasini engeller.

Kilitli kapi, key alinmadan semantic target olarak enumerate edilmez. Bu durumda kapi sadece yol gibi transit hucredir. Key alindiktan sonra veya kapi basta aciksa door semantic target olarak planlara girebilir.

Toplanmamis item node'lari segment icinde terminal/blok gibi davranir. Toplanmis item node'lari ise sonraki segmentlerde normal yol gibi transit gecilebilir. Bu sayede `start -> key -> stamina -> door` gibi bir plan, `stamina -> door` segmentinde daha once toplanmis key hucrelerinden gecebilir.

Exact dead planlar skorlanirken ilk basarisiz semantic segmente kadar kisalabilir. Farkli full suffix'ler ayni basarisiz prefix'e dusuyorsa bu planlar tekillestirilir; terminalde ayni dead route birden fazla basilmamalidir.

Plan sayisi icin artik yapay bir `max_semantic_plans` limiti yoktur. Ayni non-door semantic node tekrar ziyaret edilmedigi icin plan sayisi sonludur.

## Semantic Plan Verisi

Her plan `SemanticSolutionPlan` ile temsil edilir.

Alanlar:
- `steps`: semantic adimlar
- `semantic_success`: bu semantic siralama exact olarak oyunu bitirebiliyor mu
- `shortest_cost`: plan exact basariliysa HC3 graph ustundeki minimum cozum maliyeti
- `final_stamina`: plan exact basariliysa bu semantic plan sonunda kalan stamina

Her adim `SemanticPlanStep` tasir:
- `node_id`
- `position`
- `kind`
- `edge_cost`
- `remaining_stamina`

Ornek:

```text
0. start@(1, 1) edge_cost=0 stamina_after=40
1. item:key@(5, 9) edge_cost=12 stamina_after=28
2. item:stamina@(6, 13) edge_cost=9 stamina_after=25
3. door@(9, 13) edge_cost=10 stamina_after=15
```

## Segment Ajani

Fonksiyon:

```python
simulate_segment_agent(...)
```

Bir segment ajani sadece su gorevi yapar:

```text
source semantic node -> target semantic node
```

Ornek:

```text
start -> item:key
```

Ajanin bilgisi:
- grid'i bilir
- source pozisyonunu bilir
- target pozisyonunu bilir
- kendi segmentindeki visited hucreleri bilir
- baska semantic node'larin blok oldugunu bilir
- kalan stamina degerini bilir

Bu ajan insan oyuncunun tam simuluasyonu degil; iki semantic node arasindaki yerel yol bulma zorlugunu olcen stochastic heuristic ajandir.

## Semantic Blocking

Bir segmentte target disindaki henuz toplanmamis item semantic node'lari duvar gibi davranir. Daha once toplanmis item node'lari normal yol gibi gecilebilir.

Ornek segment:

```text
start -> item:key
```

Bu segmentte:
- `item:key` hedef oldugu icin girilebilir
- diger stamina item'lar bloktur
- kapi aktif degilse yol gibi transit gecilebilir
- kapi aktifse ve target degilse bloktur

Eger key daha once toplanmis olsaydi, key hucreleri sonraki segmentlerde blok olmazdi.

Bu kural, ajanlarin baska item'larin ustunden transit gecerek segment mantigini bozmasini engeller.

## Kapi Davranisi

Bu projede kapali kapi normal oyunda transit hucredir. Agent segment sampling de ayni kurali izler.

Kural:
- kapi kapali/inaktifse semantic target degildir ve yol gibi gecilebilir
- kapi acik/aktifse artik semantic target anlamina gelir
- kapi aktifken segment target'i degilse bloklanir
- kapi aktifken segment target'i ise girilebilir ve basari hedefidir

Bu ayrim onemli:
- `start -> item:key` segmentinde kilitli kapi aradaysa ajan kapinin ustunden gecebilir
- `item:key -> item:stamina` segmentinde kapi artik aktifse ve target degilse ajan kapidan transit gecmez
- `item:key -> door` segmentinde kapi target oldugu icin girilebilir

## Ajan Hareket Kurali

Her adimda ajan 4-neighbor hucrelere bakar.

Gecerli komsu:
- walkable olmali
- semantic blocker olmamali
- veya dogrudan target olmali

Secim sirasi:

1. Target komsu hucreyse dogrudan target'a gider.
2. Daha once ziyaret edilmemis komsular varsa rastgele birini secer.
3. Tum secenekler daha once ziyaret edilmisse, geldigi hucre disindaki seceneklerden rastgele secer.
4. Sadece geldigi hucreye donebiliyorsa oraya doner ve `forced_backtracks += 1`.

Bu kuralin amaci:
- ajan mumkun oldugunca yeni yollari denesin
- ziyaret edilmis alanlarda da tamamen basarisiz sayilmasin
- cikmaz sokakta geri donmeyi olcebilsin

## Revisit ve Forced Backtrack

Ajan daha once bastigi bir hucreye tekrar basarsa:

```text
revisits += 1
```

Ajan sadece geldigi hucreye donebildigi icin geri donuyorsa:

```text
forced_backtracks += 1
```

Bu iki metrik ayri tutulur.

Sebep:
- `revisits` genel dolanmayi olcer
- `forced_backtracks` cikmaz sokak etkisini olcer

Bir forced backtrack cogu zaman ayni zamanda revisit de olur. Bu beklenen bir durumdur.

## Failure Kurali

Bu modelde failure sadece stamina bitmesiyle olur.

Yani:
- ajan hedefe ulasirsa success
- hedefe ulasmadan stamina 0 olursa failure

Segment target'a tam `0 stamina` ile varmak success kabul edilir.

Ek max step limit yoktur. Her adim stamina tukettigi icin stamina dogal bir ust sinirdir.

## Segment Result

Her ajan `SegmentAgentResult` dondurur.

Alanlar:
- `success`
- `start_stamina`
- `remaining_stamina`
- `total_steps`
- `revisits`
- `forced_backtracks`

Bu veri sadece ilgili segment icindir. Tum oyun boyunca global visited gecmisi tutulmaz.

## Segment Population

Fonksiyon:

```python
simulate_segment_population(...)
```

Bir segment icin birden fazla ajan calistirir.

Onemli parametre:

```python
incoming_stamina_samples
```

Bu, o segmente gelen ajanlarin baslangic stamina dagilimidir.

Ilk segmentte bu dagilim:

```python
(initial_stamina,)
```

seklindedir.

Sonraki segmentlerde ise onceki segmentten basarili cikan ajanlarin kalan stamina degerleri kullanilir.

## Sample Propagation

Bu modelin en onemli kismi sample propagation'dir.

Ornek plan:

```text
start -> item:stamina -> door
```

Ilk segment:

```text
start -> item:stamina
```

Diyelim 100 ajan calisti ve 80 tanesi basarili oldu.

Basarili ajanlarin kalan stamina degerleri:

```text
[12, 10, 9, 14, ...]
```

Target node bir stamina item oldugu icin her basarili sample'a item degeri eklenir.

Stamina item degeri 6 ise:

```text
[18, 16, 15, 20, ...]
```

Bu yeni liste, sonraki segmentin giris dagilimidir:

```text
item:stamina -> door
```

Sonraki segmentte yine `agents_per_segment` kadar ajan calisir. Her ajan baslangic stamina degerini bu sample listesinden random secer.

Secim replacement ile yapilir. Yani ayni sample birden fazla ajan tarafindan kullanilabilir.

## Neden Replacement ile Sample Seciliyor

Ornek:

```text
start -> S1
```

100 ajan calisti, 80 basari var.

Sonraki segmentte yine 100 ajan calistirmak istiyorsak 80 sample'dan 100 baslangic degeri uretmemiz gerekir.

Bu yuzden replacement kullanilir.

Avantaj:
- her segmentte sabit sayida ajan calisir
- segment success rate'leri daha karsilastirilabilir olur
- basarili sample dagilimi sonraki segmente tasinir

## Plan Basari Orani

Her segmentin kendi success rate'i vardir.

Ornek:

```text
start -> key: 0.80
key -> stamina: 0.50
stamina -> door: 0.75
```

Plan basari orani:

```text
0.80 * 0.50 * 0.75 = 0.30
```

Kodda:

```python
estimated_success_rate *= segment_summary.success_rate
```

Eger plan exact olarak cozulemezse:

```text
estimated_success_rate = 0
```

Bu durumda o plan icin ajan calistirilmez. Plan main route ortalamasina katilmaz; ilk exact basarisiz segment dead segment hesabina katilir.

## Map Difficulty Skoru

Bir haritada birden fazla semantic door plan olabilir.

Exact cozulebilen planlar simule edilir.

Exact cozulemeyen planlar:
- simule edilmez
- main route success ortalamasina dahil edilmez
- dead segment hesabina dahil edilir

Ana route seviyesinde sadece exact cozulebilen planlarin ortalama success rate'i kullanilir:

```text
main_route_success_rate = average(success rates of exact solvable plans)
```

Difficulty:

```text
main_route_difficulty = 1 - main_route_success_rate
```

Yorum:
- cozulebilen route'lar kolay geciliyorsa main route difficulty dusuk olur
- cozulebilen route'lar zor geciliyorsa main route difficulty yuksek olur
- exact dead planlar bu ana ortalamayi bozmaz

## Segment Balance

Main route difficulty tek basina yeterli degildir. Ornek:

```text
start -> key success = 1.0
key -> door success = 0.5
route success = 0.5
```

Bu route hedef difficulty'ye denk gelebilir ama zorluk tek segmente yigilmistir.

Bu nedenle unique simule edilmis segmentlerin success rate standart sapmasi hesaplanir. Agent success rate `0` olan ama exact olarak gecilebilir segmentler de bu hesaba dahildir.

```text
segment_success_std = std(unique attempted segment success rates)
```

Segment ayni source-target ciftinde birden fazla route icinde gecerse tek unique segment olarak ele alinir. Birden fazla olcum varsa o segmentin ortalama success rate'i kullanilir.

Yorum:
- `segment_success_std` dusukse zorluk dengeli dagilmis demektir
- `segment_success_std` yuksekse bazi segmentler cok kolay, bazilari cok zor demektir

## Dead Segment Ratio

Exact cozulemeyen full route'lari dogrudan tek tek cezalandirmak ayni kok problemi fazla sayabilir.

Ornek:

```text
start -> S1 basarisiz
start -> S1 -> key -> door dead
start -> S1 -> S2 -> key -> door dead
```

Bu durumda asil problem `start -> S1` segmentidir. Bu yuzden deadness unique segment seviyesinde sayilir:

```text
dead_segment_ratio = dead_unique_segments / all_unique_segments
```

Buradaki `all_unique_segments` tum suffix route parcalarini kapsamaz. Sadece:
- agent tarafindan gercekten simule edilen segmentler
- exact cozulemeyen planlarda ilk basarisiz semantic segment

dahil edilir.

Bir segment exact cozulebilen bir route icinde simule edildiyse, agent success rate `0` olsa bile dead segment sayilmaz. Bu durumda segment balance listesine `0.0` olarak girer. Dead segment sadece exact semantic analizde ilk basarisiz segment olarak gelen segmenttir.

## Deterministic Randomness

Ajan hareketinde random secim vardir. Bu yuzden ayni state iki kere degerlendirilirse farkli sonuc cikma riski vardir.

MCMC energy icin bu iyi degildir. Ayni haritanin ayni energy degerini uretmesi gerekir.

Bu yuzden segment seed'i deterministik uretilir.

Seed girdileri:
- global agent seed
- plan node sirasi
- segment index
- source position
- target position

Kod:

```python
segment_seed = _stable_seed(
    (
        "segment",
        config.random_seed,
        plan.node_ids,
        segment_index,
        source_node.position,
        target_node.position,
    )
)
```

Bu yapi su sonucu verir:
- ayni map ve ayni config ayni sonucu uretir
- farkli semantic plan veya farkli segment farkli random akis kullanir
- MCMC energy daha stabil olur

## Cache

Agent difficulty sonuclari cache'lenir.

Cache key sunlari icerir:
- grid
- start
- door
- item turleri, pozisyonlari ve degerleri
- initial stamina
- locked door
- agent config

Bu sayede ayni state tekrar degerlendirilirse ajan simulasyonu yeniden calismaz.

## Energy ile Baglanti

Agent difficulty energy su formulu kullanir:

```text
E =
  difficulty_weight * abs(main_route_difficulty - target_agent_difficulty)
  + segment_balance_weight * segment_balance_score
  + dead_segment_weight * dead_segment_ratio
  + final_stamina_weight * final_stamina_score
  + spacing_weight * spacing_score
```

Burada:

```text
main_route_difficulty = 1 - main_route_success_rate
segment_balance_score = min(1, 2 * segment_success_std)
target_final_stamina = final_stamina_target_factor * initial_stamina * (1 - target_agent_difficulty)
weighted_final_stamina = sum(plan_success_rate * avg_final_stamina_for_plan) / sum(plan_success_rate)
final_stamina_score = min(1, abs(target_final_stamina - weighted_final_stamina) / max(1, initial_stamina))
grid_scale = sqrt(grid_width * grid_height)
spacing_target = spacing_target_scale * grid_scale * (0.5 + 0.5 * target_agent_difficulty)
spacing_score = min(1, abs(spacing_target - spacing_actual) / (2 * spacing_target_scale * grid_scale))
```

Pipeline parametreleri:

```python
STAMINA_ENERGY_MODEL = "agent_difficulty"
TARGET_AGENT_DIFFICULTY = 0.5
AGENT_DIFFICULTY_WEIGHT = 20.0
SEGMENT_BALANCE_WEIGHT = 10.0
DEAD_SEGMENT_WEIGHT = 10.0
FINAL_STAMINA_WEIGHT = 10.0
FINAL_STAMINA_TARGET_FACTOR = 0.8
SPACING_WEIGHT = 10.0
SPACING_TARGET_SCALE = 1.5
AGENTS_PER_SEGMENT = 30
AGENT_DIFFICULTY_SEED = 12345
```

Eski baseline energy halen durur.

Kullanmak icin:

```python
STAMINA_ENERGY_MODEL = "baseline"
```

secilir.

## Terminal Ciktisi

Agent difficulty acikken energy breakdown icinde su alanlar gorunur:

```text
target_agent_difficulty
main_route_difficulty
main_route_success_rate
main_route_term
segment_success_std
segment_balance_score
segment_balance_term
dead_segment_ratio
dead_segment_term
target_weighted_final_stamina
weighted_final_stamina
final_stamina_score
final_stamina_term
spacing_target
spacing_actual
spacing_score
spacing_term
```

Ayrica `Agent difficulty summary` blogu basilir.

Ornek:

```text
Agent difficulty summary (best):
semantic_plans=10 simulated_plans=4 main_route_success_rate=0.080 best_success_rate=0.120 main_route_difficulty=0.920 segment_success_std=0.210 dead_segment_ratio=0.300 dead_segments=3/10
best_plan=start -> item:key -> item:stamina -> door estimated_success_rate=0.060
segment=0 (1, 1)->(5, 9) success_rate=0.800 avg_steps=33.87 avg_revisits=3.03 avg_backtracks=0.60 avg_success_stamina=20.17
segment=1 (5, 9)->(7, 13) success_rate=0.133 avg_steps=15.87 avg_revisits=0.87 avg_backtracks=0.10 avg_success_stamina=26.00
```

Bu cikti segment bazinda zorlugun nereden geldigini okumayi saglar.

Burada:
- `semantic_plans`: door'a giden tum simple semantic plan sayisi
- `simulated_plans`: exact olarak cozulebildigi icin ajan calistirilan plan sayisi
- `main_route_success_rate`: exact cozulebilen planlarin ortalama success rate'i
- `best_success_rate`: en yuksek success rate'e sahip planin orani
- `segment_success_std`: unique simule edilmis segment success rate'lerinin standart sapmasi
- `dead_segment_ratio`: unique dead segment orani

## Mevcut Sinirlilik

Bu model ilk surumdur.

Su an:
- exact cozulebilen door-ending semantic planlar main route difficulty icin kullanilir
- exact cozulemeyen semantic planlar dead segment ratio ile temsil edilir
- unique simule edilmis segmentler segment balance icin kullanilir; agent success rate `0` olan exact-gecilebilir segmentler dahil edilir
- revisit ve forced backtrack metrikleri energy'ye dogrudan eklenmez
- ajanlar sadece local segment davranisi simule eder

Bunlar bilincli sadelestirmelerdir. Segment istatistikleri zaten tutuldugu icin ileride energy fonksiyonuna eklenmeleri kolaydir.
