# Stamina-Only HC3 Model

Bu belge sade stamina-only HC3 modelini tanimlar.

Bu versiyonda:
- canavar yok
- power item yok
- stamina itemlari var
- kapi acik olabilir veya anahtar gerektirebilir
- kapali kapi gecilemez; anahtar alinana kadar duvar gibi davranir

Amac:

Baslangictan aktif kapiya, stamina negatife dusmeden ulasan en az bir gecerli senaryo var mi?

Kapiya tam son adimda `stamina = 0` ile ulasmak basari sayilir.

## Oyun Kurallari

### Hucre Turleri

- duvar
- normal yol
- baslangic
- stamina itemi
- anahtar
- kapi

### Kapi Semantigi

Kapi kapaliyken:
- hucre gecilemez
- basari uretmez
- normal yol gibi transit kullanilamaz
- BFS ve ajan simulasyonu icin duvar gibi bloklanir

Kapi acikken veya anahtar alindiktan sonra:
- kapi hedef hucre olur
- oraya ulasmak basari sayilir
- target olmayan segmentlerde transit gecis olarak kullanilmaz

Bu karar, haritanin kapali kapi arkasindaki bolgelerini anahtar alinmadan erisilebilir sayma hatasini engeller.

Ek uretim kurali:
- kapi hucre si blok kabul edildiginde start, kapi disindaki tum walkable hucrelere erisebilmelidir
- yani kapi haritanin iki bolgesini birbirine baglayan tek kopru olamaz
- bu sayede kapinin arkasinda oyun boyunca hic kullanilamayacak buyuk alanlar olusmaz

## Semantic Node Tanimi

Semantic node'lar:
- `start`
- her `stamina item`
- `key`
- aktif `door`

Aktif `door`:
- kapi bastan aciksa aktiftir
- kapi kilitliyse ancak anahtar alindiktan sonra aktiftir

Kapali kapi:
- semantic target degildir
- transit hucre degildir
- BFS icinde bloklu hucredir

## Edge Tanimi

Bir semantic node'dan diger semantic node'lara edge uretmek icin BFS kullanilir.

Her edge:
- iki semantic node arasinda olur
- agirligi iki node arasindaki en kisa yol uzunlugudur
- baska semantic node uzerinden transit gecmez
- kapali kapi uzerinden transit gecmez

## BFS Kurali

Bir kaynak node'dan BFS baslatilirken:
- duvarlara girilmez
- kapali kapiya girilmez
- normal yol hucrelerine girilir
- target disindaki henuz toplanmamis semantic item node'lari terminal/blok gibi davranir
- aktif kapi hedef olarak kaydedilir ve o hucrenin otesine BFS devam etmez

Bu kuralin amaci:
- item ustunden habersiz transit gecmeyi engellemek
- kapali kapi arkasini anahtar alinmadan erisilebilir saymamak
- semantic planlari gercek oyun akisi ile uyumlu tutmak

## State Tanimi

Arama state'i sunlari tutar:
- `current_node`
- `remaining_stamina`
- `collected_items_mask`
- `has_key`

`has_key`, `collected_items_mask` icinden turetilebilir ama uygulamada acik alan olarak tutulur.

## Transition Kurali

Bir state'ten yeni state'e gecmek icin:
1. Bulunulan node'dan cikilabilecek semantic node'lar mevcut kapi durumuna gore BFS ile bulunur.
2. Her hedef node icin shortest-path maliyeti alinir.
3. `remaining_stamina >= edge_cost` ise gecis denenebilir.
4. Hedef node stamina item ise stamina eklenir.
5. Hedef node key ise `has_key = True` olur.
6. Hedef node kapi ise kapi aktif oldugu icin basari uretilir.

Kapiya ulasildiginda `remaining_stamina = 0` kabul edilir.

## Success Condition

Harita cozulebilir sayilir eger en az bir state:
- aktif kapi node'una ulasabiliyorsa
- bu ulasim sirasinda stamina negatife dusmuyorsa

Son kontrol:

```text
remaining_stamina >= 0
```

## Neden Bu Model Exact?

Bu sade problemde yol maliyeti sadece stamina tuketimidir.

Canavar ve power olmadigi icin:
- ayni iki semantic node arasindaki daha uzun bir yolun
- daha kisa yola gore kaynak acisindan avantaji yoktur

Bu yuzden semantic node'lar arasinda en kisa yol bilgisi yeterlidir.

Model exact olur cunku:
- semantic node uzerinden transit yasaktir
- kapali kapi uzerinden transit yasaktir
- shortest path mevcut kapi durumuna gore hesaplanir
- alinmis item bilgisi state icinde tutulur
- kapi yalnizca aktif oldugunda hedef sayilir

## Ozet

1. Haritadaki anlamli noktalari semantic node olarak sec.
2. Node'lar arasindaki shortest path mesafelerini BFS ile bul.
3. Baska semantic node'larin ustunden transit gecme.
4. Kapali kapiyi duvar gibi blokla.
5. `node + stamina + collected items + key` state'i ile arama yap.
6. Aktif kapiya stamina negatife dusmeden ulasilabiliyorsa HC3 saglanir.
