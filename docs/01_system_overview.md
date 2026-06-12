# Sistem Ozeti

Bu proje, grid tabanli bir kacis oyunu icin gecerli ve hedeflenen zorluk profiline yakin haritalar uretir. Uretim akisi Monte Carlo / MCMC benzeri kucuk state degisiklikleriyle calisir.

## Modlar

### `door_only`

En basit baseline moddur.

Kurallar:
- haritada sadece `start` ve `door` kritik ogelerdir
- stamina yoktur
- item yoktur
- kapi aciktir

Amac:
- topolojik olarak gecerli bir maze uretmek
- `start -> door` en kisa yol uzunlugunu hedefe yaklastirmak

### `stamina_only`

`door_only` modun stamina, key ve kilitli kapi iceren versiyonudur.

Kurallar:
- `start` vardir
- bir `door` vardir
- kapi kilitli olabilir
- bir `key` olabilir
- bir veya daha fazla `stamina` item olabilir
- canavar yoktur
- power item yoktur

Guncel kapi karari:
- kapali kapi transit yol degildir
- anahtar alinana kadar duvar gibi bloklanir
- kapi bastan aciksa veya anahtar alindiysa aktif hedef olur
- aktif kapiya `0 stamina` ile ulasmak basari sayilir

Bu karar HC3 solver, semantic plan enumeration, agent segment simulation ve spacing enerji hesabinda ayni sekilde uygulanir.

## Ana Dosyalar

### `baseline_pipeline.py`

Baseline uretim, initial state secimi, proposal hamleleri ve MCMC akisidir.

### `utils/hard_constraints/hc3_stamina_only_solver.py`

`stamina_only` modeli icin exact solvability kontrolu yapar.

### `utils/agent_difficulty.py`

Semantic planlari enumerate eder ve her segmentte heuristic ajan simulasyonlari calistirir.

### `utils/energy_functions.py`

Door-only energy, stamina-aware baseline energy ve agent difficulty energy fonksiyonlarini icerir.

### `main.py`, `viz_maze.py`, `play_maze.py`

Harita gorsellestirme, debug overlay ve oynanabilir Pygame akisini tasir.

## Genel Calisma Akisi

1. Baslangic icin gecerli bir state uretilir.
2. Bu state icin energy hesaplanir.
3. MCMC adimlarinda kucuk proposal hamleleri denenir.
4. Candidate state hard constraint'leri sagliyorsa energy hesaplanir.
5. Metropolis-Hastings kuralina gore kabul veya red verilir.
6. En iyi gorulen state ayrica saklanir.
7. `viz_maze.py` veya `play_maze.py` ile final/best state incelenebilir.
