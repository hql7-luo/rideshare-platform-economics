# Strategy memo / 策略备忘录

**Independent project · Perspective: Uber strategy analyst / 假设视角：Uber 策略分析师**

Data through 2026-08; recent window 2025-09–2026-08. Nominal USD; gross take is before platform costs. / 数据截至 2026-08，最近窗口 2025-09—2026-08；金额为名义美元，毛额抽成未扣平台成本。

**1. Test price changes against driver pay and retention / 定价试验同时看司机收入与留存**

Uber's mean fare changed +73.5% since 2019-02, versus +38.2% for driver pay; latest take rate is 21.8%. Test by zone and hour; track completions, repeat usage and driver supply alongside gross take. This historical gap does not establish pricing power.

自 2019-02，Uber 平均车费变动 +73.5%，司机收入变动 +38.2%；最新抽成率为 21.8%。 按区域与时段做小规模定价试验，同时看完成单量、复购、司机供给和毛额抽成；历史增速差不能直接证明提价空间。

**2. Allocate supply by wait time, including airport trips / 按等待时间配置运力，单独看机场**

Airport-linked trips were 8.4% of Uber trips in the latest 12 months, with 6.2-minute valid mean waits and 30.9% gross take rate. Pilot supply incentives where waits persist. Measure completions, driver pay including incentives, and platform contribution after incentives using internal data.

最近 12 个月，机场关联订单占 Uber 的 8.4%，有效平均等待 6.2 分钟，毛额抽成率 30.9%。 按区域和时段的等待情况试验运力激励；衡量完成率、计入激励后的司机收入，并用内部数据核对扣除激励后的平台贡献。

**3. Evaluate short trips in dollars as well as take rates / 短途单同时看比例与每单金额**

Uber trips up to 2 miles had a 30.4% gross take rate, but just $3.96/trip versus $6.43 overall; 10.0% paid drivers above base fare. Prioritize pickup efficiency before broad minimum-fare increases. Test rider retention and driver pay; negative gross take alone does not establish a net loss.

Uber 不超过 2 英里的订单抽成率 30.4%，但每单仅 $3.96，整体为 $6.43；10.0% 的订单司机收入高于基础车费。 优先缩短接驾，再考虑广泛调高最低车费；测试留存并遵守司机支付要求。负抽成不能直接当作净亏损。

**4. Separate the congestion fee from platform pricing / 把拥堵费和平台定价分开评估**

Uber zone-linked fare/trip changed +11.0%, pay/trip +7.6%, and take/trip +19.4%. The recorded CBD charge averaged $1.50 per charged trip. Itemize the passenger fee and monitor demand, pay and take separately. Controlled tests are needed to identify economic incidence.

Uber 区内关联订单每单车费变动 +11.0%，司机收入 +7.6%，毛额抽成 +19.4%；被收费订单平均记录 CBD 费用 $1.50。 清晰列出乘客附加费，分开监测需求、司机收入与抽成；用对照试验识别经济负担归属。

**Limits / 局限**

Descriptive hypotheses, not causal effects: pricing, minimum-pay changes and trip mix confound comparisons. Gross take is not profit; incentives/discounts may be incomplete. The inferred proxy includes Newark and zone 105 from just one and two training pickups, respectively; it also misses through-trips. Economic incidence remains unidentified. Evidence: `data/results/key_numbers.json` and result CSVs.

这是描述性假设；价格、最低收入与订单结构混杂，毛额抽成不是利润，优惠和激励可能遗漏。推断代理因训练月仅 1、2 单就纳入 Newark 与区域 105，还会漏掉穿区订单；经济负担归属无法识别。数字见 key_numbers.json 与结果表。
