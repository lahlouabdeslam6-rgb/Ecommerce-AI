export type OrchestratorAgentResult = {
  agent: string;
  status: string;
  data: Record<string, unknown>;
};

export type OrchestratorResponse = {
  detected_intent: string;
  selected_agents: string[];
  results: OrchestratorAgentResult[];
  requires_confirmation: boolean;
  proposed_action: string | null;
};

export type OrchestratorHistoryItem = OrchestratorResponse & {
  id: number;
  actor_id: number | null;
  actor_email: string | null;
  actor_role: string;
  message: string;
  created_at: string;
};

export type OrchestratorHistory = {
  items: OrchestratorHistoryItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
};
