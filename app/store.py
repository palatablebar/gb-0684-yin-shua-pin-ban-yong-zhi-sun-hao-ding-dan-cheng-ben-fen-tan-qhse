import sqlite3,json,os
from pathlib import Path
from app.errors import DomainError

def connection():
    path=Path(os.environ.get('DB_PATH','data/records.db'));path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path,timeout=10);db.row_factory=sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, body TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, decision TEXT NOT NULL DEFAULT "待复核")')
    db.execute('CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY,value TEXT NOT NULL)')
    return db

def save(run_id, body):
    with connection() as db:
        db.execute('INSERT OR IGNORE INTO runs(id,body) VALUES (?,?)',(run_id,json.dumps(body,ensure_ascii=False)))
        db.execute("INSERT INTO meta(key,value) VALUES ('latest',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(run_id,))
    return get(run_id)

def get(run_id):
    with connection() as db:r=db.execute('SELECT * FROM runs WHERE id=?',(run_id,)).fetchone()
    if not r:raise DomainError('NOT_FOUND','批次不存在',404)
    body=json.loads(r['body']);body.update(run_id=r['id'],review_version=r['version'],decision=r['decision']);return body

def history():
    with connection() as db:rows=db.execute("SELECT id,version,decision FROM runs ORDER BY CASE WHEN id=(SELECT value FROM meta WHERE key='latest') THEN 0 ELSE 1 END,rowid DESC LIMIT 100").fetchall()
    return [dict(r) for r in rows]

def review(run_id, version, decision):
    if decision not in ('通过','退回'):raise DomainError('DECISION','复核状态无效')
    with connection() as db:
        cur=db.execute('UPDATE runs SET version=version+1,decision=? WHERE id=? AND version=?',(decision,run_id,version))
        if cur.rowcount!=1:
            if not db.execute('SELECT 1 FROM runs WHERE id=?',(run_id,)).fetchone():raise DomainError('NOT_FOUND','批次不存在',404)
            raise DomainError('STALE','复核版本已更新，请刷新',409)
    return get(run_id)

def save_revision(state):
    """修订结算单落库。
    幂等：同一 run_id（同基线+同修订输入+同规则版本）重跑直接返回既有单，不新增差额。
    可恢复：写入前备份当前 latest，任何步骤失败则回滚到旧版，不丢记录、不污染 latest。"""
    run_id=state['run_id']
    with connection() as db:
        existing=db.execute('SELECT body FROM runs WHERE id=?',(run_id,)).fetchone()
        if existing:
            return get(run_id)  # 同修订重跑：复用首版结算，差额不重复入账
        db.execute('CREATE TABLE IF NOT EXISTS run_backups (run_id TEXT, body TEXT NOT NULL, version INTEGER NOT NULL, decision TEXT NOT NULL, backed_up_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
        latest=db.execute("SELECT value FROM meta WHERE key='latest'").fetchone()
        backup=None
        if latest:
            backup=db.execute('SELECT * FROM runs WHERE id=?',(latest['value'],)).fetchone()
        try:
            db.execute('INSERT INTO runs(id,body) VALUES (?,?)',(run_id,json.dumps(state,ensure_ascii=False)))
            db.execute('INSERT INTO run_backups(run_id,body,version,decision) VALUES (?,?,?,?)',
                (backup['id'],backup['body'],backup['version'],backup['decision'])) if backup else None
            db.execute("INSERT INTO meta(key,value) VALUES ('latest',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(run_id,))
            # 落库后立即重算指纹自检，失败则抛出触发整事务回滚
            from app.modules.m7_archive import export_out
            if export_out.revision_checksum(state)!=state.get('archive',{}).get('sha256'):
                raise DomainError('ARCHIVE','归档指纹自检失败')
        except Exception:
            db.rollback()
            if backup:  # 恢复旧版 latest，保证记录不丢
                db.execute("INSERT INTO meta(key,value) VALUES ('latest',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(backup['id'],))
            raise
    return get(run_id)

def backups():
    with connection() as db:
        db.execute('CREATE TABLE IF NOT EXISTS run_backups (run_id TEXT, body TEXT NOT NULL, version INTEGER NOT NULL, decision TEXT NOT NULL, backed_up_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
        rows=db.execute('SELECT run_id,version,decision,backed_up_at FROM run_backups ORDER BY rowid DESC LIMIT 20').fetchall()
    return [dict(r) for r in rows]
