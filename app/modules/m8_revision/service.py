from app.modules.m8_revision.rules import settle

def execute(state):
    baseline=state.pop('_baseline_state')
    return settle(state,baseline)
