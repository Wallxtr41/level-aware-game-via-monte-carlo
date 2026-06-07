# Energy Fonksiyonlari

Bu dosya, projedeki energy fonksiyonlarinin neyi olctugunu aciklar.

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

Yeni agent difficulty energy sadece ajan tabanli zorluk terimini kullanir. Bu modelde `target_path` ve `target_final_stamina` energy hesabina girmez.

Formul:

```text
E = w_difficulty * |D_agent - D_target|
```

Burada:
- `D_agent`: segment ajan simulasyonlarindan tahmin edilen zorluk
- `D_target`: hedef zorluk
- `w_difficulty`: difficulty teriminin agirligi

`baseline_pipeline.py` icindeki ilgili parametreler:
- `TARGET_AGENT_DIFFICULTY`
- `AGENT_DIFFICULTY_WEIGHT`
- `AGENTS_PER_SEGMENT`
- `AGENT_DIFFICULTY_SEED`

## Agent Difficulty Nasil Hesaplaniyor

Once HC3 semantic graph uzerinden door'a giden tum simple semantic planlar cikarilir.

Ornek planlar:
- `start -> door`
- `start -> item:key -> door`
- `start -> item:stamina -> item:key -> door`

Exact olarak cozulemeyen planlar da listede kalir. Bu planlar icin ajan calistirilmaz ve plan success rate `0` kabul edilir.

Exact olarak cozulebilen planlarda her plan segmenti icin ajanlar calistirilir.

Ornek segmentler:
- `start -> item:key`
- `item:key -> item:stamina`
- `item:stamina -> door`

Her segmentte ajanlar:
- hedef node'a ulasmaya calisir
- diger semantic node'lari duvar gibi gorur
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

Map seviyesinde:

```text
D_agent = 1 - average_plan_success_rate
```

Yani door'a giden tum semantic planlarin ortalama gecilme orani dusukse harita daha zor kabul edilir.

## Deterministic Randomness

Ajanlar stochastic davranir ama ayni state ayni energy degerini uretmelidir.

Bu yuzden ajan simulasyonlarinda kullanilan random seed:
- global agent seed
- plan node sirasi
- segment source/target bilgisi

uzerinden deterministik uretilir.

Bu sayede ayni harita tekrar degerlendirildiginde ayni agent difficulty sonucu alinir.

