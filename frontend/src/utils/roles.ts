export const ROLE_MAP: Record<string, { name: string; emoji: string; faction: string }> = {
  seer: { name: "预言家", emoji: "🔮", faction: "good" },
  witch: { name: "女巫", emoji: "🧙", faction: "good" },
  hunter: { name: "猎人", emoji: "🏹", faction: "good" },
  guard: { name: "守卫", emoji: "🛡️", faction: "good" },
  villager: { name: "村民", emoji: "🏠", faction: "good" },
  werewolf: { name: "狼人", emoji: "🐺", faction: "wolf" },
  white_wolf_king: { name: "白狼王", emoji: "👑", faction: "wolf" },
};

export const PHASE_MAP: Record<string, string> = {
  setup: "准备中",
  role_assignment: "角色分配",
  night_begin: "夜晚开始",
  guard_action: "守卫行动",
  wolf_discuss: "狼人讨论",
  witch_action: "女巫行动",
  seer_action: "预言家行动",
  night_resolve: "夜间结算",
  dawn: "天亮",
  first_day_sheriff_gate: "第一天",
  sheriff_election: "警长竞选",
  sheriff_speech: "警长发言",
  sheriff_vote: "警长投票",
  sheriff_result: "警长结果",
  death_skill: "死亡技能",
  sheriff_transfer: "警徽移交",
  last_words: "遗言",
  win_check: "胜负判定",
  discuss_order: "发言顺序",
  discuss: "白天讨论",
  vote: "放逐投票",
  vote_result: "投票结果",
  tie_speech: "平票发言",
  tie_vote: "平票投票",
  exile: "放逐",
  no_elimination: "无人出局",
  self_destruct: "自爆",
  day_aborted: "白天终止",
  game_end: "游戏结束",
};

export const EVENT_TYPE_MAP: Record<string, string> = {
  phase_change: "阶段切换",
  role_assignment: "角色分配",
  night_action: "夜间行动",
  night_resolution: "夜间结算",
  dawn: "天亮",
  sheriff_election: "警长竞选",
  vote: "投票",
  sheriff_result: "警长结果",
  death: "死亡",
  death_skill: "死亡技能",
  sheriff_transfer: "警徽移交",
  last_words: "遗言",
  game_end: "游戏结束",
  discuss_order: "发言顺序",
  speech: "发言",
  exile: "放逐",
  no_elimination: "无人出局",
  reasoning_trace: "思维过程",
};

export function getRoleInfo(roleId: string) {
  return ROLE_MAP[roleId] || { name: roleId, emoji: "❓", faction: "unknown" };
}

export function getPhaseName(phase: string) {
  return PHASE_MAP[phase] || phase;
}

export function getEventTypeName(type: string) {
  return EVENT_TYPE_MAP[type] || type;
}
