# Testler ve Genişletme Fikirleri

Bu dosya, mevcut doğrulama yaklaşımını ve ileride geliştirilebilecek yönleri toplar.

## Mevcut Testler

Önemli test dosyaları:
- [test_agent_difficulty.py](../test_agent_difficulty.py)
- [test_hc3_stamina_only_solver.py](../test_hc3_stamina_only_solver.py)
- [test_hc3_solver.py](../test_hc3_solver.py)
- [test_hard_constraints.py](../test_hard_constraints.py)

## `stamina_only` Solver Testlerinde Ne Kontrol Ediliyor

Temel olarak şu davranışlar test edilir:
- locked door + key ile çözülebilir durum
- yetersiz stamina veya mantıksız yerleşim nedeniyle çözülemez durum
- semantic node’ların üstünden fark edilmeden geçilmeme mantığı
- graph cache kullanımının doğru çalışması

## Agent Difficulty Testlerinde Ne Kontrol Ediliyor

Ajan modelinin detaylı algoritmik açıklaması:
- [08_agent_difficulty_model.md](08_agent_difficulty_model.md)

`test_agent_difficulty.py` şu davranışları kontrol eder:
- birden fazla semantic door plan çıkarılabiliyor mu
- exact çözülemeyen semantic planlar success rate `0` olarak ortalamaya katılıyor mu
- stamina item hedef node olduğunda item etkisi sonraki segment başlangıcına taşınıyor mu
- aynı problem ve aynı config ile agent difficulty sonucu deterministic kalıyor mu

## Terminal Debug Bilgileri

Şu anda debug için önemli iki çıktı türü vardır:

### 1. Energy breakdown
Bu çıktı, toplam energy’nin hangi terimlerden oluştuğunu gösterir.

### 2. Solution summary
Bu çıktı, semantic çözüm adımlarını listeler:
- hangi node’a gidildi
- edge cost neydi
- o adımdan sonra kaç stamina kaldı

## Mevcut Güçlü Yanlar

- `stamina_only` HC3 exact çözücüye sahip
- energy artık semantik yapıyı hissediyor
- agent difficulty energy ile segment bazlı zorluk tahmini yapılabiliyor
- proposal seti sadece topology değil item ve door hareketlerini de içeriyor
- görselleştirme tarafında çözüm overlay’i var

## Mevcut Sınırlılıklar

### 1. Başlangıç state üretimi hâlâ tam genel değil
Şu an yapıcı ama nispeten basit bir seed generation var.

### 2. Proposal ağırlıkları uniform
Belki ileride weighted move selection daha iyi davranabilir.

### 3. Difficulty model hâlâ ilk sürüm
Agent difficulty şu an door'a giden tüm semantic planların ortalama başarı oranını temel alıyor.

İleride:
- segment revisit / backtrack baskısı
- başarısız segmentlerin stamina kayıp profili

energy'ye ayrıca eklenebilir.

### 4. Full oyun modeli henüz tamamlanmadı
Şu an:
- canavar yok
- power yok
- locked door geçilebilir kabul ediliyor

Bu, bilinçli olarak seçilmiş sade bir alt model.

## Doğal Sonraki Adımlar

### 1. Constructive initial state generator’ı daha da iyileştirmek
Başlangıç state üretimi artık candidate-pool ve energy-aware seçim kullanıyor.

Sonraki olası iyileştirmeler:
- maze topolojisini de target difficulty'ye göre constructive üretmek
- low difficulty için daha az dallanan ana koridorlar üretmek
- high difficulty için branch/loop yoğunluğunu kontrollü artırmak
- initial candidate pool'u adaptive yapmak

### 2. Energy’ye yeni terimler eklemek
Örnek:
- key baskısı
- ilk stamina item’a erişim zorluğu
- exploration baskısı
- fazla güvenli çözümlere ceza
- agent revisit / forced backtrack terimleri

### 3. Proposal dağılımını ağırlıklı yapmak
Örneğin:
- topology daha sık
- door move daha seyrek
- item move orta sıklıkta

### 4. Incremental recomputation
Özellikle graph cache ve bazı analizleri tek hücre değişimlerinden sonra kısmen reuse etmek.

### 5. Full HC3 modeline ilerlemek
İleride tekrar:
- monsters
- power
- çok kaynaklı tradeoff

eklenirse, daha genel resource-aware solver devreye alınabilir.
