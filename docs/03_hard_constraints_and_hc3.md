# Hard Constraints ve HC3

Bu dosya, harita uretiminde kullandigimiz hard constraint mantigini aciklar.

## HC1

HC1 temel connectivity constraint'idir.

Amac:
- `start` noktasindan walkable bolgelerin kopuk adaciklara ayrilmamasini saglamak
- topology proposal'lari sonrasi haritanin temel baglantililigini korumak

Not: HC1 ham grid uzerinden calisir. Kilitli kapinin oyun semantigindeki blok etkisi HC3 tarafinda uygulanir.

## Door Partition Constraint

Kapali kapi bloklu oldugu ve aktif kapiya girildiginde oyun bittigi icin, kapinin arkasinda yalnizca kapidan gecilerek erisilebilen buyuk alanlar olusmamali.

Bu yuzden pipeline ek bir hard constraint uygular:
- door hucre si gecici olarak blok kabul edilir
- start'tan BFS calistirilir
- door disindaki tum walkable hucreler hala start'tan erisilebilir olmalidir

Bu constraint kapinin graph icinde articulation/bridge gibi davranmasini engeller. Kapi cikmaz sokak sonunda olabilir; fakat haritanin baska bir bolgesine tek gecis noktasi olamaz.

## HC2

HC2 istenmeyen `2x2` acik bloklari engeller.

Amac:
- maze yapisinin fazla oda benzeri bloklara donusmemesi
- corridor agirlikli yapiyi korumak

## HC3 Nedir

HC3, haritanin oyun kurallarina gore gercekten cozulebilir olup olmadigini test eder.

`stamina_only` mod icin HC3:
- gerekirse key alinabilmeli
- stamina itemlariyla birlikte stamina butcesi yetmeli
- kapali kapi anahtar alinana kadar gecilememeli
- kapi aktif hale geldikten sonra kapiya varilabilmeli
- kapiya `0 stamina` ile varmak kabul edilmeli

Bu sadece geometrik `start -> door` path kontrolu degildir; resource ve item toplama sirasini da iceren exact state-space search problemidir.

## Semantic Node Graph

Solver tum grid'i hucre hucre brute-force gezmez. Once semantic node'lar olusturulur:
- `start`
- tum item'lar
- `door`

Sonra node'lar arasindaki edge'ler BFS ile bulunur.

Kural:
- baska semantic node uzerinden transit gecilmez
- toplanmamis item hedef degilse terminal/blok gibi davranir
- kapali kapi BFS icinde duvar gibi bloklanir
- aktif kapi hedef node olur ve onun otesine BFS devam etmez

Bu sayede item ustunden habersiz gecme ve kapali kapi arkasini yanlislikla erisilebilir sayma hatasi engellenir.

## Closed Door ve Open Door Adjacency

Solver iki mod dusunur:
- closed-door mode: kapi bloktur, target degildir
- open-door mode: kapi target olarak erisilebilir

Runtime state icinde `has_key` false ise closed-door davranisi, true ise open-door davranisi uygulanir. Kapi bastan aciksa direkt open-door davranisi kullanilir.

## Solver State

Solver state alanlari:
- `node_id`
- `remaining_stamina`
- `collected_items_mask`
- `has_key`

`collected_items_mask` hangi item'larin toplandigini tutar. `has_key`, kapi davranisini belirler.

## Transition

Bir state'ten hedef semantic node'a gecis:
1. Mevcut kapi durumuna gore reachable semantic edge'ler hesaplanir.
2. Edge cost kadar stamina duser.
3. Stamina negatife duserse gecis iptal edilir.
4. Hedef item ise etkisi uygulanir.
5. Hedef key ise `has_key = True` olur.
6. Hedef aktif door ise success uretilir.

## Dominance / Pruning

Solver ayni soyut imza icin daha kotu state'leri tutmaz.

Imza:
- `node_id`
- `collected_items_mask`
- `has_key`

Bu imza sabitken daha dusuk veya esit stamina'ya sahip state, daha yuksek stamina'li state tarafindan domine edilir.

## Cozum Analizi

`analyze_stamina_only_hc3(...)` su bilgileri dondurur:
- `shortest_success_path_length`
- `best_remaining_stamina`
- `solution_steps`

Bu veriler energy fonksiyonunda ve gorsellestirme overlay'inde kullanilir.
