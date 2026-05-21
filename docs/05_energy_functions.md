# Energy Fonksiyonları

Bu dosya, projedeki energy fonksiyonlarının neyi ölçtüğünü açıklar.

## Neden Energy Var

MCMC zincirinin bir candidate state’i “iyi” ya da “kötü” olarak değerlendirebilmesi için sayısal bir hedef gerekir.

Bu hedefe energy diyoruz.

Genel kural:
- energy ne kadar düşükse state o kadar iyi

## 1. `door_only` Energy

Bu eski baseline energy’dir.

Formül:

`E = |L - L_target|`

Burada:
- `L`: `start -> door` en kısa yol uzunluğu
- `L_target`: hedef path uzunluğu

Özellikler:
- sadece geometrik kısa yol uzunluğuna bakar
- item, stamina, key gibi semantik bilgi yoktur

Bu yüzden sadece `door_only` mod için uygundur.

## 2. `stamina_only` Baseline Energy

Bu yeni energy, `stamina_only` HC3 analizini kullanır.

Formül:

`E = w_path * |P - P_target| + w_stamina * |S - S_target|`

Burada:
- `P`: geçerli başarılı çözüm yolları içindeki en kısa başarılı çözüm maliyeti
- `P_target`: hedef çözüm uzunluğu
- `S`: başarılı çözümde kapıya varınca elde kalan en iyi stamina
- `S_target`: hedef final stamina
- `w_path`: path ağırlığı
- `w_stamina`: stamina ağırlığı

Şu an varsayılanlar:
- `w_path = 1.0`
- `w_stamina = 1.0`

## `P` Nasıl Hesaplanıyor

Solver başarılı bir senaryo bulduğunda:

`success_path_length = initial_stamina + collected_stamina - remaining_stamina`

Bu değer aslında oyuncunun toplam harcadığı hareket maliyetini temsil eder.

Sebep:
- başlangıçta belli bir stamina ile başlıyoruz
- yolda stamina item’ları topluyoruz
- sonunda bir miktar stamina kalıyor

Dolayısıyla:
- elde edilen toplam stamina kaynağı
- eksi finalde kalan stamina
- bize yürüyüş maliyetini verir

## `S` Nasıl Hesaplanıyor

Başarılı çözümler arasında:
- kapıya varıldığında elde kalan en yüksek stamina

seçilir.

Bu değer, haritanın oyuncuya ne kadar “rahat” bir çözüm sunduğunu ölçmeye yarar.

## Neden İki Terim Var

Sadece çözüm uzunluğunu hedeflemek bazen yeterli olmaz.

Örnek:
- iki harita da aynı çözüm uzunluğuna sahip olabilir
- ama birinde oyuncu kapıya `0 stamina` ile varır
- diğerinde `14 stamina` ile varır

Bu iki haritanın hissi farklıdır.

Bu yüzden:
- path hedefi
- final stamina hedefi

ayrı ayrı tutulur.

## Çözülemez Haritalar

Eğer solver haritanın çözülemez olduğunu söylerse:
- energy = `infinity`

olur.

Bu sayede MCMC böyle state’leri tercih etmez.

## Energy Breakdown

Kodda sadece toplam energy değil, terimlere ayrılmış hali de üretilir.

`stamina_only` modda terminal çıktısında şu alanlar görülür:
- `target_path`
- `path`
- `path_term`
- `target_final_stamina`
- `final_stamina`
- `stamina_term`
- `total`

Bu debug açısından çok yararlıdır.

## Şu Anki Sınırlılık

Bu baseline energy henüz şu tür ek terimleri içermiyor:
- key’e olan mesafe için özel ceza
- ilk stamina item’a erişim baskısı
- exploration baskısı
- dead-end sayısı
- fazla kolaylık / fazla bolluk cezası

Yani mevcut energy, iyi bir baseline’dır ama nihai difficulty modeli değildir.

