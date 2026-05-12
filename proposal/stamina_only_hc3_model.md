# Stamina-Only HC3 Model

Bu belge, sadeleştirilmiş HC3 modelini tanımlar.

Bu versiyonda:

- canavar yok
- power item yok
- yalnızca stamina itemları var
- kapı açık olabilir veya anahtar gerektirebilir
- kapalı kapı geçilebilir bir hücredir

Amaç:

Başlangıçtan kapıya, stamina bitmeden ulaşan en az bir geçerli senaryo var mı?

Kapıya tam son adımda `stamina = 0` ile ulaşmak başarı sayılır.

## Oyun Kuralları

### 1. Hücre Türleri

- duvar
- normal yol
- başlangıç
- stamina itemı
- anahtar
- kapı

### 2. Kapı Semantics

Kapı kapalıyken:

- hücre geçilebilirdir
- başarı üretmez
- normal yol gibi transit kullanılabilir

Kapı açıkken veya anahtar alındıktan sonra:

- kapı hedef hücre olur
- oraya ulaşmak başarı sayılır

Bu modelde kapalı kapı bir bariyer değildir.

## Node Tanımı

Semantic node’lar şunlardır:

- `start`
- her `stamina item`
- `key`
- aktif `door`

Burada aktif `door` şu anlama gelir:

- kapı baştan açıksa door node aktiftir
- kapı kapalıysa, anahtar alınana kadar door node aktif değildir

Önemli karar:

- kapalı kapı node değildir
- kapalı kapı sadece walkable transit hücredir

## Edge Tanımı

Bir semantic node’dan diğer semantic node’lara edge üretmek için BFS kullanılır.

Her edge:

- iki semantic node arasında olur
- ağırlığı, o iki node arasındaki en kısa yol uzunluğudur

## BFS Kuralı

Bir kaynak node’dan BFS başlatılırken:

- duvarlara girilmez
- normal yol hücrelerine girilir
- kapalı kapı hücresi normal yol gibi geçilebilir
- başka semantic node’ya ulaşıldığında o node hedef olarak kaydedilir
- ama o semantic node’nun ötesine BFS devam etmez

Bu kuralın amacı:

- semantic node’ların üstünden “habersiz transit” yapılmasını engellemek
- örneğin bir stamina itemının üzerinden geçip almamış gibi davranmamak

Yani semantic node’lar BFS için terminal noktalardır.

## State Tanımı

Arama state’i şunları tutar:

- `current_node`
- `remaining_stamina`
- `collected_items_mask`
- `has_key`

Not:

- `has_key`, istersek `collected_items_mask` içinden türetilebilir
- ama ayrı tutmak uygulamada daha temiz olabilir

## Transition Kuralı

Bir state’ten yeni bir state’e geçmek için:

1. Bulunulan node’dan çıkılabilecek semantic node’lar BFS ile bulunur.
2. Her hedef node için shortest-path maliyeti alınır.
3. Eğer `remaining_stamina >= edge_cost` ise geçiş mümkündür.
4. Hedef node’ya gidildiğinde:
   - stamina item ise stamina eklenir
   - key ise `has_key = True` olur
   - kapı ise başarı kontrolü yapılır

Kapıya ulaşıldığında `remaining_stamina = 0` olması kabul edilir.

## Success Condition

Harita çözülebilir sayılır eğer en az bir state:

- aktif kapı node’una ulaşabiliyorsa
- ve bu ulaşım sırasında stamina negatife düşmüyorsa

Bu modelde son kontrol:

- `remaining_stamina >= 0`

şeklindedir.

## Neden Bu Model Exact?

Bu sade problemde yol maliyeti sadece stamina tüketimidir.

Canavar ve power olmadığı için:

- aynı iki node arasındaki daha uzun bir yolun
- daha kısa yola göre ayrı bir avantajı yoktur

Bu yüzden semantic node’lar arası en kısa yol bilgisi yeterlidir.

Model exact olur çünkü:

- semantic node üzerinden transit yasaktır
- shortest path doğru hesaplanır
- alınmış item bilgisi state içinde tutulur
- kapı yalnızca aktif olduğunda hedef sayılır

Bu nedenle solver:

- çözülebilir diyorsa gerçekten çözülebilirdir
- çözülemez diyorsa gerçekten çözülemezdir

## Özet

Bu sade modelin temel fikri:

1. Haritadaki anlamlı noktaları semantic node olarak seç.
2. Node’lar arası shortest path mesafelerini BFS ile bul.
3. Başka semantic node’ların üstünden transit geçme.
4. `node + stamina + collected items + key` state’i ile arama yap.
5. Aktif kapıya stamina negatife düşmeden ulaşılabiliyorsa HC3 sağlanır.
