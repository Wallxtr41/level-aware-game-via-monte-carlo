# Görselleştirme ve Solution Overlay

Bu dosya, `main.py` ve `viz_maze.py` içindeki görselleştirme mantığını açıklar.

## `main.py`

`main.py`, daha çok tek bir maze layout’u temel oyun görselleriyle göstermek için kullanılır.

Görsel öğeler:
- wall tile
- road tile’lar
- door sprite
- item sprite’ları
- player sprite

Çizim sırası:
1. zemin / background tile
2. item overlay
3. player overlay

Kapı davranışı:
- kapı hücresi doğrudan background gibi çizilir
- yani kapı ayrı bir floating overlay değil

Item davranışı:
- item’lar yol tile’ının üstüne merkezlenerek çizilir

## `viz_maze.py`

`viz_maze.py`, `baseline_pipeline` ile MCMC çalıştırır ve ortaya çıkan state’i gösterir.

Ayarlanabilir temel parametreler:
- `MODE`
- `DISPLAY_STATE`
- `MCMC_STEPS`
- `RANDOM_SEED`

## Seed Davranışı

`RANDOM_SEED` için iki kullanım vardır:
- belirli bir sayı verilirse aynı sonuç yeniden üretilebilir
- `None` verilirse her çalıştırmada yeni bir random seed seçilir

Seçilen gerçek seed, pencere başlığında gösterilir.

## Solution Overlay

`stamina_only` modda çözüm yolu ayrıca renkli overlay olarak çizilir.

Amaç:
- solver’ın bulduğu çözümün görsel olarak takip edilebilmesi

## Overlay Nasıl Üretiliyor

1. Önce energy breakdown içinden `solution_steps` alınır.
2. Bu adımlar semantic seviyededir:
   - `start`
   - `item:key`
   - `item:stamina`
   - `door`
3. Sonra bu semantic adımların her iki komşu çifti arasında grid üstünde gerçek path yeniden bulunur.
4. Bu path’ler segment segment çizilir.

## Neden Segment Mantığı Kullanılıyor

Çözüm yolu tek renkte çizilseydi:
- hangi kısım start’tan key’e gidiyor
- hangi kısım key’den stamina item’a gidiyor
- hangi kısım kapıya gidiyor

ayırt etmek zor olurdu.

Bu yüzden:
- her semantic geçiş ayrı segment
- her segment ayrı renk

olarak çizilir.

## Semantic Blocking

Path yeniden bulunurken önemli bir kural vardır:
- başka semantic node’ların içinden yanlışlıkla transit geçiş yapılmaz

Bu, solver mantığıyla uyum sağlamak için yapılır.

Örneğin:
- start’tan stamina item’a giden segment
- yolda key’in içinden transit geçerek çizilmez

Bu sayede overlay ile solver çözümü tutarlı kalır.

## Çizim Sırası

`viz_maze.py` içinde çizim sırası:
1. arka plan tile’ları
2. item sprite’ları
3. solution overlay
4. player sprite

Bu sıralama sayesinde:
- item’lar görünür kalır
- çözüm yolu da net okunur
- player üstte kaldığı için start kolay seçilir

