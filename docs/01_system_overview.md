# Sistem Özeti

Bu proje, grid tabanlı bir kaçış oyunu için harita üretmeyi amaçlar. Ana fikir, geçerli ve hedeflenen zorluk profiline yakın haritaları Monte Carlo / MCMC benzeri bir arama ile üretmektir.

Şu an sistem iki ayrı mod destekler:

## 1. `door_only`

Bu en ilkel baseline moddur.

Kurallar:
- haritada sadece `start` ve `door` kritik öğelerdir
- stamina yoktur
- item yoktur
- kapı açıktır

Bu modda amaç:
- topolojik olarak geçerli bir maze üretmek
- `start -> door` en kısa yol uzunluğunu hedefe yaklaştırmak

## 2. `stamina_only`

Bu mod, `door_only` modun daha zengin bir versiyonudur.

Kurallar:
- `start` vardır
- bir `door` vardır
- kapı kilitli olabilir
- bir `key` olabilir
- bir veya daha fazla `stamina` item olabilir
- canavar yoktur
- power item yoktur

Bu modun en kritik semantiği:
- kapalı kapı geçilebilir
- yani kapalı kapı duvar gibi davranmaz
- sadece kapı hücresine ulaşmak başarı için yetmez
- başarı için kapının aktif hale gelmiş olması gerekir
- kapı aktif olma koşulu:
  - ya kapı baştan açıktır
  - ya da anahtar alınmıştır

Ek olarak:
- kapıya tam `0 stamina` ile ulaşmak başarı sayılır

## Ana Dosyalar

### `baseline_pipeline.py`
Mevcut baseline üretim ve MCMC akışını taşır.

### `utils/hard_constraints/hc3_stamina_only_solver.py`
`stamina_only` model için exact solvability kontrolü yapar.

### `utils/energy_functions.py`
Hem eski basit energy fonksiyonunu hem de yeni stamina-aware baseline energy’yi içerir.

### `main.py`
Rastgele bir maze layout’un Pygame ile temel görselleştirmesini yapar.

### `viz_maze.py`
`baseline_pipeline` ile üretilen final veya best state’i Pygame içinde gösterir. Çözüm yolu overlay’i de buradadır.

## Genel Çalışma Akışı

Sistemin üst düzey akışı şöyledir:

1. Başlangıç için geçerli bir state üretilir.
2. Bu state için energy hesaplanır.
3. MCMC adımlarında küçük proposal hamleleri denenir.
4. Yeni candidate state constraint’leri sağlıyorsa energy hesaplanır.
5. Metropolis-Hastings kuralı ile kabul veya red verilir.
6. En iyi görülen state ayrıca saklanır.
7. `viz_maze.py` ile final ya da best state görselleştirilebilir.

