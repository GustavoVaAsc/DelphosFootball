// Rules of the language model's display name: any Qwen 3.5 id, with or
// without its namespace and in any case, reads "Qwen 3.5"; an unknown id has
// no name, so the interface never prints a raw model id.
import 'package:delphos_frontend/ui/core/labels/llm_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('every Qwen 3.5 id is named Qwen 3.5', () {
    for (final id in [
      'qwen3.5-9b',
      'qwen/qwen3.5-9b',
      'Qwen/Qwen3.5-35B-A3B',
      'QWEN3.5',
    ]) {
      expect(llmModelName(id), 'Qwen 3.5', reason: id);
    }
  });

  test('another model or a missing id has no name', () {
    expect(llmModelName('qwen2.5-7b'), isNull);
    expect(llmModelName('acme/foo-7b'), isNull);
    expect(llmModelName(''), isNull);
    expect(llmModelName(null), isNull);
  });
}
