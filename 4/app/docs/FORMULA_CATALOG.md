# Каталог формул

Все денежные результаты TCO — USD на партию, CFLP — руб./год. Конвертация валют применяется только к CBAM.

1. `freight = Σ distance_km * tariff_usd_tkm * volume_tons`.
2. `insurance = volume_tons * price_usd_per_ton * insurance_rate`.
3. `inventory = volume_tons * price_usd_per_ton * wacc * lead_time_days / 365`.
4. `risk = p_fail * l_fail_loss_usd`; упаковка из исходного JSON.
5. `transport_emissions_per_t = Σ distance_km * emission_g_tkm * 1e-6`.
6. `tax_eur = max(0, see_prod + transport_emissions_per_t - benchmark) * volume_tons * (ets_eur-origin_eur)`.
7. `border_usd = tax_eur * eur_usd_rate`.
8. `TCO_log = freight + insurance + inventory + packaging + risk + border`; `TCO_total = V*P + TCO_log`.
9. `P* = Δ(freight+border)*365/(V*WACC*Δt)` при одинаковых остальных компонентах. При WACC=0 корень отсутствует, если постоянные части различны.
10. Общий линейный корень: `x* = lo - f(lo)*(hi-lo)/(f(hi)-f(lo))`; статус CROSSING только внутри диапазона. Равные постоянные функции: IDENTICAL_IN_RANGE; разные: NO_CROSSING_IN_RANGE.
11. `ETS* = Origin + (V*P*WACC*Δt/365 - Δfreight)/(V*FX*ΔE)`; отрицательное значение не используется как допустимая цена ETS.
12. CFLP: `min ΣF_j y_j + Σc_ji x_ji`; `Σ_j x_ji=d_i`; `Σ_i x_ji<=K_j*y_j`.
13. SSCFLP: `z_ji∈{0,1}`, `x_ji=d_i*z_ji`, `Σ_j z_ji=1`, `z_ji<=y_j`.
14. LP gap: `abs(Zmilp-Zlp)/abs(Zmilp)*100`; 0/0→0; ненулевое/0→null.
15. Температурная длительность эпизода: `n * interval_minutes`; непрерывность требует точного номинального шага. SCRAP только при одном эпизоде `duration>30`.
16. `norm_g=sqrt(ax²+ay²+az²)`; шок `max(abs(ax),abs(ay),abs(az))>2.5`.
17. Haversine: `a=sin²((φ2-φ1)/2)+cosφ1*cosφ2*sin²((λ2-λ1)/2)`; `d=2R*atan2(sqrt(a),sqrt(1-a))`, R=6371.0088км.
18. `Scope3=D_accepted_km*E_rail_g_tkm*1e-6*volume_tons`, тCO2.
19. Dynamic TCO: `ΔTCO=(1-p_base)*L_fail`; стоимость партии повторно не включается в логистический TCO.

Ссылки по страницам и контрольным тестам — SOURCE_AUDIT.md. Все зависимости линейны в отдельном варьируемом параметре; перегибы и асимптоты отсутствуют.
