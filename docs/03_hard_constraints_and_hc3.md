# Hard Constraints ve HC3

Bu dosya, harita üretiminde kullandığımız constraint mantığını açıklar.

## HC1

HC1 temel connectivity constraint’idir.

Amaç:
- `start` noktasından tüm gerekli walkable bölgelere erişimin kopmaması
- haritanın anlamsız kopuk adacıklara ayrılmaması

Pratikte:
- duvar açma / kapama hamleleri sonrasında haritanın bağlantılı kalıp kalmadığı kontrol edilir

## HC2

HC2, açık alanların belirli bir estetik/topolojik kısıtını korur.

Mevcut haliyle:
- istenmeyen `2x2` açık blok oluşumları engellenir

Amaç:
- maze yapısının fazla “oda” benzeri bloklara dönüşmemesi
- daha corridor ağırlıklı bir yapı korunması

## HC3 Nedir

HC3, haritanın oyun kurallarına göre gerçekten çözülebilir olup olmadığını test eder.

Bu, sadece geometrik olarak kapıya yol var mı sorusu değildir.

`stamina_only` mod için HC3 şu anlamdadır:
- gerekirse anahtar alınabilmeli
- stamina item’larıyla birlikte oyuncu stamina bütçesi yetmeli
- kapı aktif hale geldikten sonra kapıya varılabilmeli
- kapıya `0 stamina` ile varmak da kabul

## Neden HC3 Zor

HC3, HC1 ve HC2’ye göre daha zordur çünkü:
- sadece grid topolojisine bakmaz
- item toplama sırasını önemser
- kalan stamina’yı önemser
- anahtar alınıp alınmadığını önemser

Yani bu artık düz graph reachability değil, state-space search problemidir.

## `stamina_only` HC3 Solver Mimarisi

İlgili dosya:
- [utils/hard_constraints/hc3_stamina_only_solver.py](../utils/hard_constraints/hc3_stamina_only_solver.py)

Bu solver exact çalışır.

### Exact ne demek

Exact solver demek:
- “çözülebilir” dediyse gerçekten çözülebilir
- “çözülemez” dediyse gerçekten çözülemez

Yani heuristic tahmin değildir.

## Semantic Node Graph Mantığı

Bu sade modelde solver, tüm grid üstünde hücre hücre brute-force dolaşmaz.

Önce semantic node’lar oluşturulur:
- `start`
- tüm item’lar
- `door`

Sonra bu semantic node’lar arasında adjacency çıkarılır.

Önemli kural:
- bir semantic node’dan diğerine giderken
- başka semantic node’nun içinden transit geçiş yapılmaz

Bu sayede:
- item üstünden fark etmeden geçip onu yok sayma hatası oluşmaz
- çözüm adımları daha temiz modellenir

## Closed Door ve Open Door Adjacency

Solver iki ayrı adjacency tutar:
- `closed_door_adjacency`
- `open_door_adjacency`

Sebep:
- kapı kapalıyken transit hücre olabilir ama terminal olmayabilir
- kapı aktif olduğunda ise hedef semantic node olur

Bu ayrım solver’ın kapı aktif olmadan onu “başarı” sanmamasını sağlar.

## Solver State

Solver state şu alanlardan oluşur:
- `node_id`
- `remaining_stamina`
- `collected_items_mask`
- `has_key`

Burada:
- `collected_items_mask`, hangi item’ların toplandığını tutar
- `has_key`, key alınmış mı bilgisini açık taşır

## Transition

Bir solver state’ten komşu semantic node’a geçerken:

1. edge cost kadar stamina düşer
2. hedef node bir item ise ve ilk kez alınıyorsa etkisi uygulanır
3. hedef node key ise `has_key = True`
4. hedef node stamina item ise `+item.value` kadar stamina eklenir
5. hedef node kapı ise ve kapı aktifse başarı kontrol edilir

## Dominance / Pruning

Solver, aynı soyut imza için daha kötü state’leri tutmaz.

İmza şu parçaları içerir:
- `node_id`
- `collected_items_mask`
- `has_key`

Bu imza sabitken:
- daha düşük ya da eşit stamina’ya sahip bir state
- daha yüksek stamina’ya sahip başka bir state tarafından domine edilir

Bu pruning sayesinde gereksiz senaryolar elenir.

## Çözüm Analizi

Solver sadece solvable / unsolvable demekle kalmaz.

`analyze_stamina_only_hc3(...)` ile şu bilgiler de alınır:
- `shortest_success_path_length`
- `best_remaining_stamina`
- `solution_steps`

Bu veriler energy fonksiyonunda ve görselleştirme overlay’inde kullanılır.

