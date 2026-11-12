// Tests for ReportViewModel: the stored report on open, generation with its
// elapsed seconds, cancelling (by the user, by a player switch, by closing),
// errors with a retry of the same request, and the regenerate flag.
import 'dart:async';

import 'package:delphos_frontend/ui/features/explorer/view_models/report_status.dart';
import 'package:delphos_frontend/ui/features/explorer/view_models/report_view_model.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../../support/report_backend.dart';
import '../../../support/report_fixtures.dart';

void main() {
  late ReportsBackend backend;
  late ReportViewModel vm;

  setUp(() {
    backend = ReportsBackend();
    vm = ReportViewModel(reports: backend.repository);
  });

  testWidgets('opening a player shows the stored report', (tester) async {
    backend.stored = reportJson('llm', playerId: 1);
    vm.show(1);
    expect(vm.status, ReportStatus.checking);
    await tester.pump();
    expect(vm.status, ReportStatus.ready);
    expect(vm.report?.id, 7);
    vm.dispose();
  });

  testWidgets('generating counts seconds, then shows the report', (
    tester,
  ) async {
    vm.show(1);
    await tester.pump();
    expect(vm.status, ReportStatus.none);
    vm.generate();
    expect(vm.status, ReportStatus.generating);
    await tester.pump(const Duration(seconds: 3));
    expect(vm.elapsedSeconds, 3);
    expect(backend.generationBodies, [
      {'player_id': 1, 'report_type': 'scouting', 'force_regenerate': false},
    ]);
    backend.answer();
    await tester.pump();
    expect(vm.status, ReportStatus.ready);
    expect(vm.report?.id, 9);
    await tester.pump(const Duration(seconds: 2));
    expect(vm.elapsedSeconds, 3);
    vm.dispose();
  });

  testWidgets('cancelling keeps the previous report', (tester) async {
    backend.stored = reportJson('llm', playerId: 1);
    vm.show(1);
    await tester.pump();
    vm.regenerate();
    expect(vm.status, ReportStatus.generating);
    vm.cancel();
    expect(vm.status, ReportStatus.ready);
    backend.answer();
    await tester.pump(const Duration(seconds: 2));
    expect(vm.report?.id, 7);
    expect(vm.elapsedSeconds, 0);
    vm.dispose();
  });

  testWidgets('a player switch or closing cancels the generation', (
    tester,
  ) async {
    vm.show(1);
    await tester.pump();
    vm.generate();
    vm.show(2);
    expect(vm.status, ReportStatus.checking);
    await tester.pump();
    vm.generate();
    vm.show(null);
    expect(vm.status, ReportStatus.idle);
    backend.answer();
    await tester.pump();
    expect(vm.status, ReportStatus.idle);
    expect(vm.report, isNull);
    vm.dispose();
  });

  testWidgets('a failed regeneration retries with the same flag', (
    tester,
  ) async {
    backend
      ..stored = reportJson('llm', playerId: 1)
      ..failGenerate = true;
    vm.show(1);
    await tester.pump();
    vm.regenerate();
    await tester.pump();
    backend.answer();
    await tester.pump();
    expect(vm.status, ReportStatus.error);
    expect(vm.generationFailed, isTrue);
    backend.failGenerate = false;
    unawaited(vm.retry());
    expect(vm.status, ReportStatus.generating);
    await tester.pump();
    backend.answer();
    await tester.pump();
    expect(vm.status, ReportStatus.ready);
    expect(
      backend.generationBodies.map((b) => (b as Map)['force_regenerate']),
      [true, true],
    );
    vm.dispose();
  });

  testWidgets('a failed lookup is an error that retries the lookup', (
    tester,
  ) async {
    backend.failLookup = true;
    vm.show(1);
    await tester.pump();
    expect(vm.status, ReportStatus.error);
    expect(vm.generationFailed, isFalse);
    backend.failLookup = false;
    unawaited(vm.retry());
    expect(vm.status, ReportStatus.checking);
    await tester.pump();
    expect(vm.status, ReportStatus.none);
    expect(backend.generationBodies, isEmpty);
    vm.dispose();
  });
}
