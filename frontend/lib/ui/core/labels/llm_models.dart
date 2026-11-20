/// The display name of the language model that wrote a report. The backend
/// sends a raw model id ("qwen/qwen3.5-9b"); the interface only ever prints
/// the name this map gives it, never the id.
library;

/// Id prefixes (lower case, after any `namespace/`) and their names.
const Map<String, String> _modelNames = {'qwen3.5': 'Qwen 3.5'};

/// The name for [modelId], or `null` for a missing or unknown id.
String? llmModelName(String? modelId) {
  if (modelId == null) return null;
  final id = modelId.toLowerCase().split('/').last;
  for (final MapEntry(:key, :value) in _modelNames.entries) {
    if (id.startsWith(key)) return value;
  }
  return null;
}
