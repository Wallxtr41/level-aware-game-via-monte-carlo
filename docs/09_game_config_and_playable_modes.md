# Game Config ve Oynanabilir Modlar

Bu dosya difficulty-aware stamina modu icin eklenen temel oynanis config'ini ve yeni oynanabilir script'i aciklar.

## Config Kaynagi

Temel ayarlar:
- [utils/game_config.py](../utils/game_config.py)

Ana config alanlari:
- `TARGET_AGENT_DIFFICULTY`: 0.0 - 1.0
- `PLAYER_VISION_RADIUS`: 1 - 5
- `GRID_WIDTH`: 9 - 31
- `GRID_HEIGHT`: 9 - 25
- `DOOR_REQUIRES_KEY`: `True` veya `False`
- `STAMINA_ITEM_COUNT`: 0 - 3
- `STAMINA_ITEM_VALUE`: 1 - 50

`START_POS` bu user-facing config'e alinmadi; oyun hala varsayilan `(1, 1)` baslangicini kullanir.

## Runtime Uygulama

`baseline_pipeline.py` artik su fonksiyonla runtime config alabilir:

```python
bp.apply_difficulty_stamina_config(config)
```

Bu fonksiyon:
- grid boyutunu gunceller
- target difficulty'yi gunceller
- kapinin key isteyip istemedigini gunceller
- stamina item sayisini gunceller
- stamina item degerini `utils.game_config` uzerinden gunceller
- energy function ve mode config objelerini yeniden kurar

## Oynanabilir Script

Yeni script:
- [difficulty_stamina_game.py](../difficulty_stamina_game.py)

Calistirma:

```bash
python difficulty_stamina_game.py
```

Ana menu:
- `Custom map`: oyuncu config degerlerini girer ve seed verebilir
- `20-level campaign`: sabit seed + config presetlerinden olusan 20 bolum

## Custom Map Alanlari

Custom ekranda duzenlenen alanlar:
- difficulty
- vision radius
- maze width
- maze height
- door requires key
- stamina count
- stamina value
- seed

Seed:
- `0` yazilirsa random seed uretilir
- `0` disinda integer verilirse ayni map tekrar uretilebilir

## Campaign Mode

Campaign mode 20 fixed preset icerir. Presetler:
- seed ile sabittir
- difficulty yavas yavas artar
- bazi bolumlerde grid boyutu buyur
- key ve stamina item kullanimi ilerledikce artar

## Oyun Kontrolleri

Harita icinde:
- `WASD` veya ok tuslari: hareket
- `P`: pes et ve cozum replay'ini goster
- `R`: ayni haritayi yeniden oyna
- `M` veya `Esc`: ana menuye don
- `Q`: cikis
- campaign'de bolum kazanilinca `N`: sonraki bolum

Kapali kapi artik duvar gibi davranir. Anahtar alinmadan kapinin uzerine basilamaz.
