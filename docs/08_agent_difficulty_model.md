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

Bir segmentte target disindaki semantic node'lar duvar gibi davranir.

Ornek segment:

```text
start -> item:key
```

Bu segmentte:
- `item:key` hedef oldugu icin girilebilir
- diger stamina item'lar bloktur
- kapi aktif degilse yol gibi transit gecilebilir
- kapi aktifse ve target degilse bloktur

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

Bu durumda o plan icin ajan calistirilmez, ama plan map-level ortalamaya `0` olarak katilir.

## Map Difficulty Skoru

Bir haritada birden fazla semantic door plan olabilir.

Her plan simule edilir.

Exact cozulemeyen planlar:
- simule edilmez
- success rate `0` kabul edilir
- ortalamaya dahil edilir

Map seviyesinde tum planlarin ortalama success rate'i kullanilir:

```text
average_plan_success_rate = average(plan_success_rates)
```

Difficulty:

```text
difficulty_score = 1 - average_plan_success_rate
```

Yorum:
- door'a giden planlarin buyuk kismi kolay geciliyorsa difficulty dusuk olur
- door'a giden planlarin buyuk kismi basarisiz ya da zor ise difficulty yuksek olur
- exact cozulemeyen semantic planlar difficulty'yi artirir

Bu, onceki `best plan` yaklasimindan farklidir. Artik tek kolay plan tum haritayi kolay gostermeye yetmez; tum semantic door denemeleri ortalamaya katilir.

Ileride su alternatifler eklenebilir:
- best plan ile second-best plan farki
- revisit/backtrack agirlikli zorluk

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
E = difficulty_weight * abs(agent_difficulty - target_agent_difficulty)
```

Burada:

```text
agent_difficulty = 1 - average_plan_success_rate
```

Pipeline parametreleri:

```python
STAMINA_ENERGY_MODEL = "agent_difficulty"
TARGET_AGENT_DIFFICULTY = 0.5
AGENT_DIFFICULTY_WEIGHT = 20.0
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
agent_difficulty
average_agent_success_rate
agent_difficulty_term
```

Ayrica `Agent difficulty summary` blogu basilir.

Ornek:

```text
Agent difficulty summary (best):
semantic_plans=10 simulated_plans=4 average_success_rate=0.032 best_success_rate=0.060 difficulty=0.968
best_plan=start -> item:key -> item:stamina -> door estimated_success_rate=0.060
segment=0 (1, 1)->(5, 9) success_rate=0.800 avg_steps=33.87 avg_revisits=3.03 avg_backtracks=0.60 avg_success_stamina=20.17
segment=1 (5, 9)->(7, 13) success_rate=0.133 avg_steps=15.87 avg_revisits=0.87 avg_backtracks=0.10 avg_success_stamina=26.00
```

Bu cikti segment bazinda zorlugun nereden geldigini okumayi saglar.

Burada:
- `semantic_plans`: door'a giden tum simple semantic plan sayisi
- `simulated_plans`: exact olarak cozulebildigi icin ajan calistirilan plan sayisi
- `average_success_rate`: tum semantic planlarin ortalama success rate'i
- `best_success_rate`: en yuksek success rate'e sahip planin orani

## Mevcut Sinirlilik

Bu model ilk surumdur.

Su an:
- tum door-ending semantic planlar difficulty skoru icin kullanilir
- exact cozulemeyen semantic planlar success rate `0` olarak ortalamaya katilir
- revisit ve forced backtrack metrikleri energy'ye dogrudan eklenmez
- ajanlar sadece local segment davranisi simule eder

Bunlar bilincli sadelestirmelerdir. Segment istatistikleri zaten tutuldugu icin ileride energy fonksiyonuna eklenmeleri kolaydir.
