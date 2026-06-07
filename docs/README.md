# Monte Carlo Game Docs

Bu klasör, projede şu ana kadar kurulan algoritmik yapıyı parça parça açıklar.

Amaç:
- oyunun mevcut kurallarını netleştirmek
- `baseline_pipeline.py` içindeki MCMC akışını açıklamak
- `stamina_only` modundaki exact HC3 mantığını anlatmak
- energy fonksiyonlarının ne ölçtüğünü açıkça yazmak
- görselleştirme ve solution overlay davranışını belgelemek

Okuma sırası önerisi:
1. [01_system_overview.md](01_system_overview.md)
2. [02_map_and_state_model.md](02_map_and_state_model.md)
3. [03_hard_constraints_and_hc3.md](03_hard_constraints_and_hc3.md)
4. [04_baseline_pipeline_and_mcmc.md](04_baseline_pipeline_and_mcmc.md)
5. [05_energy_functions.md](05_energy_functions.md)
6. [06_visualization_and_solution_overlay.md](06_visualization_and_solution_overlay.md)
7. [08_agent_difficulty_model.md](08_agent_difficulty_model.md)
8. [07_tests_and_extension_ideas.md](07_tests_and_extension_ideas.md)

İlgili ek dokümanlar:
- [proposal/hc3_formalization.md](../proposal/hc3_formalization.md): daha genel HC3 fikri
- [proposal/stamina_only_hc3_model.md](../proposal/stamina_only_hc3_model.md): sade stamina-only modelin formal açıklaması
