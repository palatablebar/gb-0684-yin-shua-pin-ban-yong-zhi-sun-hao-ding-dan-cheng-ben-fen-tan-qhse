# 印刷拼版用纸损耗与订单成本分摊

面向印刷厂生产成本员，处理采信、判定、核算、复核与归档。

## 启动

```bash
docker compose up --build -d
```

访问 http://localhost:18253 。初次启动自动运行脏样例，可切换 clean.csv 与 legacy.csv。顶部“运行批次”会重新计算，同源输入复用批次。

## 业务模块

- 工单采信：`/m1_ingest`、`/api/m1_ingest`
- 纸张换算：`/m2_mapping`、`/api/m2_mapping`
- 拼版排算：`/m3_versions`、`/api/m3_versions`
- 损耗认定：`/m4_segments`、`/api/m4_segments`
- 余料结转：`/m5_calculate`、`/api/m5_calculate`
- 成本对账：`/m6_reconcile`、`/api/m6_reconcile`
- 批次归档：`/m7_archive`、`/api/m7_archive`
- 修订结算：`/m8_revision`、`/api/m8_revision`（预演）、`/api/revision_runs`（落库）、`/api/revision_archive/<id>/export.csv`

## 迟到修订工单的裁决

已放行纸批的金额与库存快照冻结，**不重开旧批**。改印量/改交期工单走独立补差结算单（ADJUST，唯一可入账）；"重开旧批"（REOPEN）只在同页生成对比视图，标记 `REOPEN_VIEW_ONLY`，绝不改写已发财务金额。减量退库、增量从基线批期末可排库存扣减，差额按带符号最大余数法分摊，逐行勾稽。同修订重跑命中幂等 ID 不新增差额；落库失败自动备份回滚到旧版。规则与口径见 `docs/DATA-DICTIONARY.md` 的"迟到修订工单结算"。修订样例：`sample_data/revision_qty.csv`、`revision_due.csv`、`revision_mix.csv`。

## 核心规则

按版面旋转比较可排数量，固定开机损耗与印量损耗分开计，再对订单做最大余数分摊。完整数值、边界和异常定义见 `docs/DATA-DICTIONARY.md`。

## 验证

```bash
docker compose exec -T app pytest -q
docker compose config --quiet
```

原始样例在 `sample_data/`。测试在 `tests/`。封存文件是单份CSV，含运行清单、计算证据、隔离原因与对账。复核需提交当前版本，陈旧复核返回409。

## 数据与限制

SQLite保存在records命名卷，普通重启与构建不会清除。确认可丢弃本项目数据后，运行 `docker compose down -v` 再启动可重置。单文件上限2MB；不接入外部业务系统；历史规则由本项目样例定义，不代表实际行业标准。
