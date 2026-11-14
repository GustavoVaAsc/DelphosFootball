/// The root widget: dependency injection with `provider` (ADR-023), the
/// es-ES locale, the theme and the router.
library;

import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';
import 'package:provider/provider.dart';

import 'data/repositories/archetype_repository.dart';
import 'data/repositories/chat_repository.dart';
import 'data/repositories/player_repository.dart';
import 'data/repositories/report_repository.dart';
import 'data/services/api_client.dart';
import 'routing/app_router.dart';
import 'routing/routes.dart';
import 'ui/core/theme/delphos_theme.dart';
import 'ui/core/view_models/dataset_view_model.dart';
import 'ui/core/widgets/focus_visibility.dart';

/// Provides the [ApiClient] and the repositories built on it to every
/// screen, then shows the routed app.
///
/// The caller owns [apiClient]: `main.dart` creates it for the page's
/// lifetime, and a test closes its own fake. This widget never closes it.
class DelphosApp extends StatefulWidget {
  const DelphosApp({super.key, required this.apiClient, this.router});

  /// The only locale the app supports: UI text is es-ES.
  static const Locale locale = Locale('es', 'ES');

  final ApiClient apiClient;

  /// Overrides the router, for tests that start at another location.
  final GoRouter? router;

  @override
  State<DelphosApp> createState() => _DelphosAppState();
}

class _DelphosAppState extends State<DelphosApp> {
  // Built once: a router rebuilt in build() would reset navigation.
  late final GoRouter _router = widget.router ?? buildAppRouter();

  @override
  void initState() {
    super.initState();
    FocusVisibility.install();
  }

  @override
  void dispose() {
    if (widget.router == null) _router.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final api = widget.apiClient;
    return MultiProvider(
      providers: [
        Provider<ApiClient>.value(value: api),
        Provider(create: (_) => PlayerRepository(apiClient: api)),
        Provider(create: (_) => ArchetypeRepository(apiClient: api)),
        Provider(create: (_) => ReportRepository(apiClient: api)),
        Provider(create: (_) => ChatRepository(apiClient: api)),
        // Dataset facts for the shell (total, season, data date), loaded
        // once at start-up.
        ChangeNotifierProvider(
          create: (_) =>
              DatasetViewModel(archetypes: ArchetypeRepository(apiClient: api))
                ..load(),
        ),
      ],
      child: MaterialApp.router(
        title: Routes.appTitle,
        debugShowCheckedModeBanner: false,
        locale: DelphosApp.locale,
        supportedLocales: const [DelphosApp.locale],
        localizationsDelegates: GlobalMaterialLocalizations.delegates,
        theme: buildDelphosTheme(),
        routerConfig: _router,
      ),
    );
  }
}
