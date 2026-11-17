TITLE='印刷拼版用纸损耗与订单成本分摊'
SHORT='printyield'
RULE_VERSION='2026.11.17-v1'
MODULES=[('m1_ingest', '工单采信'), ('m2_mapping', '纸张换算'), ('m3_versions', '拼版排算'), ('m4_segments', '损耗认定'), ('m5_calculate', '余料结转'), ('m6_reconcile', '成本对账'), ('m7_archive', '批次归档'), ('m8_revision', '修订结算')]
REVISION_SAMPLES=('revision_qty.csv','revision_due.csv','revision_mix.csv')
# 修订单允许变更的业务字段；材质/尺寸变更会破坏原批成本口径，须走新单而非修订
REVISABLE=frozenset(['quantity','due','stock','note'])
REQUIRED=['id', 'order_id', 'version', 'lot', 'paper_w', 'paper_h', 'piece_w', 'piece_h', 'bleed', 'gap', 'dimension_unit', 'grain', 'quantity', 'gsm', 'price_kg', 'fixed_loss', 'loss_pct', 'stock', 'due']
NUMERIC=['version', 'paper_w', 'paper_h', 'piece_w', 'piece_h', 'bleed', 'gap', 'quantity', 'gsm', 'price_kg', 'fixed_loss', 'loss_pct', 'stock']
DATES=['due']
TIMES=[]
