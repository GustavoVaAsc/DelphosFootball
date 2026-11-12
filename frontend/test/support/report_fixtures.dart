// Backend-shaped JSON for the /reports endpoints: one ReportResponse and the
// ReportListResponse of GET /reports.

/// A report as `POST /reports/generate` and `GET /reports/{id}` send it.
Map<String, Object?> reportJson(
  String source, {
  int id = 7,
  int playerId = 566723,
  String content = '<p><strong>Valoración.</strong> Texto.</p>',
}) => {
  'id': id,
  'player_id': playerId,
  'player_name': 'Michael Olise',
  'model_run_id': 'run_2025_v1',
  'report_type': 'scouting',
  'content': content,
  'source': source,
  'llm_model': source == 'llm' ? 'qwen/qwen3.5-9b' : null,
  'prompt_version': source == 'llm' ? 'v1-t0.7-p0.8-k20' : null,
  'created_at': '2026-11-10T18:00:00Z',
};

/// `GET /reports` with [items], newest first.
Map<String, Object?> reportListJson(List<Map<String, Object?>> items) => {
  'model_run_id': 'run_2025_v1',
  'items': items,
  'total': items.length,
};
