// Tests for DossierViewModel: the three sections load in parallel, each
// keeps its own state, a replacements 404 is "absent" rather than an error,
// a retry reloads only what failed, a late answer for an earlier player is
// dropped, and the Resumen follows the player on show.
import 'dart:async';

import 'package:delphos_frontend/data/repositories/player_repository.dart';
import 'package:delphos_frontend/data/repositories/report_repository.dart';
import 'package:delphos_frontend/ui/features/explorer/view_models/dossier_view_model.dart';
import 'package:delphos_frontend/ui/core/view_models/section_status.dart';
import 'package:delphos_frontend/ui/features/explorer/view_models/report_status.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import '../../../support/dossier_fixtures.dart';
import '../../../support/http_fakes.dart';
import '../../../support/report_fixtures.dart';

void main() {
  late List<String> requested;
  late Map<String, Completer<void>> gates;
  late Set<String> failing;
  late Set<String> missing;
  late DossierViewModel vm;

  setUp(() {
    requested = [];
    gates = {};
    failing = {};
    missing = {};
    final api = fakeApi((request) async {
      final path = request.url.path;
      requested.add(path);
      await gates[path]?.future;
      if (failing.contains(path)) {
        throw http.ClientException('offline', request.url);
      }
      if (missing.contains(path)) {
        return problemResponse(404, 'Not Found', 'none');
      }
      return jsonResponse(dossierJsonFor(path));
    });
    vm = DossierViewModel(
      players: PlayerRepository(apiClient: api),
      // The Resumen has its own fake: the paths above are the dossier's.
      reports: ReportRepository(
        apiClient: fakeApi((_) async => jsonResponse(reportListJson([]))),
      ),
    );
  });
  tearDown(() => vm.dispose());

  Future<void> settle() async {
    for (var i = 0; i < 6; i++) {
      await Future<void>.delayed(Duration.zero);
    }
  }

  test('requests profile, valuation and replacements together', () async {
    gates['/players/7'] = Completer<void>();
    vm.show(7);
    await settle();
    expect(requested.toSet(), {
      '/players/7',
      '/players/7/valuation',
      '/players/7/replacements',
    });
    expect(vm.identity.status, SectionStatus.loading);
    expect(vm.valuation.status, SectionStatus.ready);
    expect(vm.replacements.status, SectionStatus.ready);
    gates['/players/7']!.complete();
    await settle();
    expect(vm.identity.status, SectionStatus.ready);
    expect(vm.profile!.id, 7);
  });

  test('one failing section does not blank the others', () async {
    failing.add('/players/7/valuation');
    vm.show(7);
    await settle();
    expect(vm.identity.status, SectionStatus.ready);
    expect(vm.valuation.status, SectionStatus.error);
    expect(vm.replacements.value!.qualifyingCount, 3);
  });

  test('a replacements 404 is absent, not an error', () async {
    missing.add('/players/7/replacements');
    vm.show(7);
    await settle();
    expect(vm.replacements.status, SectionStatus.absent);
  });

  test('retry reloads only the sections that failed', () async {
    failing.add('/players/7/valuation');
    vm.show(7);
    await settle();
    failing.clear();
    requested.clear();
    await vm.retry();
    await settle();
    expect(requested, ['/players/7/valuation']);
    expect(vm.valuation.status, SectionStatus.ready);
  });

  test('an earlier player answering late is dropped', () async {
    gates['/players/7'] = Completer<void>();
    vm.show(7);
    vm.show(8);
    await settle();
    gates['/players/7']!.complete();
    await settle();
    expect(vm.playerId, 8);
    expect(vm.profile!.id, 8);
  });

  test(
    'null clears every section and the same player is not refetched',
    () async {
      vm.show(7);
      await settle();
      vm.show(7);
      await settle();
      expect(requested, hasLength(3));
      vm.show(null);
      expect(vm.playerId, isNull);
      expect(vm.profile, isNull);
      expect(vm.valuation.value, isNull);
    },
  );

  test('the Resumen follows the player on show', () async {
    vm.show(7);
    expect(vm.report.status, ReportStatus.checking);
    await settle();
    expect(vm.report.status, ReportStatus.none);
    vm.show(null);
    expect(vm.report.status, ReportStatus.idle);
  });
}
