from __future__ import annotations

from dataclasses import dataclass
from html import escape


@dataclass(frozen=True)
class LegalPage:
    title: str
    nav: tuple[tuple[str, str], ...]
    heading: str
    notice: str
    sections: tuple[tuple[str, str], ...]


PAGES: dict[str, dict[str, LegalPage]] = {
    "pt-BR": {
        "/privacy": LegalPage(
            "Privacidade — PrediBeacon",
            (("/", "PrediBeacon"), ("/terms", "Termos"), ("/methodology", "Metodologia")),
            "Aviso de privacidade pré-lançamento",
            "Este aviso descreve o serviço público atual. Ele será atualizado antes da ativação de contas, analytics, atribuição publicitária ou links comerciais.",
            (
                ("Uso público atual", "A PrediBeacon atualmente não oferece contas públicas de usuário, depósitos, operações, newsletters ou rastreamento de afiliados. O aplicativo não define intencionalmente cookies de publicidade ou analytics. Quando um visitante escolhe um link para uma plataforma externa, a PrediBeacon registra um identificador de clique próprio, o mercado, o contexto de campanha quando presente, a página de origem e a plataforma de destino para segurança, medição de desempenho e futura reconciliação com parceiros. Ela não registra uma operação ou depósito."),
                ("Registros técnicos", "Provedores de hospedagem e segurança podem processar dados comuns de solicitação, como endereço IP, horário, caminho solicitado, agente do usuário e informações de erro, para entregar e proteger o serviço."),
                ("Acesso administrativo", "A interface editorial privada mantém seu token apenas na memória da aba atual do navegador e não usa armazenamento local, armazenamento de sessão nem cookie de autenticação. As ações administrativas são auditadas no banco de dados do serviço."),
                ("Fontes externas", "Ao abrir um link de fonte ou plataforma, o visitante é enviado a um terceiro regido por seus próprios termos de privacidade. A PrediBeacon não controla esses serviços."),
                ("Mudanças futuras", "Antes de ativar newsletters, publicidade personalizada, atribuição remunerada por parceiros ou contas, a PrediBeacon documentará finalidade, base legal, retenção, operadores, transferências internacionais e direitos dos usuários."),
                ("Menores", "O serviço não foi projetado para incentivar menores a participar de mercados de previsão. Recursos comerciais futuros exigirão controles adequados de idade e jurisdição."),
            ),
        ),
        "/terms": LegalPage(
            "Termos — PrediBeacon",
            (("/", "PrediBeacon"), ("/privacy", "Privacidade"), ("/risk", "Divulgação de riscos")),
            "Termos pré-lançamento para uso informativo",
            "Estes termos pré-lançamento não são os termos comerciais finais. Atualmente não são oferecidos serviço pago, conta de usuário, execução de operações ou depósito. Links orgânicos para plataformas externas podem ser medidos, mas nenhuma parceria paga é apresentada sem verificação.",
            (
                ("Finalidade informativa", "A PrediBeacon agrega e explica informações públicas de mercados de previsão. Nada no serviço constitui oferta, solicitação, recomendação ou garantia."),
                ("Sem custódia ou execução", "A PrediBeacon não aceita nem mantém dinheiro de usuários, não cria contas em plataformas, não envia ordens e não liquida contratos."),
                ("Elegibilidade", "O acesso às informações não estabelece elegibilidade para usar qualquer plataforma de terceiros. Os usuários são responsáveis pelos requisitos de idade, identidade, localização e legislação aplicável."),
                ("Precisão e disponibilidade", "Os dados podem estar atrasados, incompletos ou ser corrigidos. O serviço pode alterar, suspender ou remover conteúdo para tratar erros, questões de segurança ou atualizações das fontes."),
                ("Serviços de terceiros", "Nomes e links de terceiros identificam fontes ou plataformas e não implicam propriedade, endosso ou parceria. Aplicam-se os termos separados desses terceiros."),
                ("Uso aceitável", "Os usuários não devem atacar o serviço, contornar controles de acesso, fazer coleta automatizada de forma prejudicial, deturpar conteúdo, manipular mercados nem usar a PrediBeacon para violar a lei ou direitos de terceiros."),
                ("Propriedade intelectual", "A marca PrediBeacon, as explicações originais e o software permanecem protegidos. Fatos de fontes e marcas de terceiros permanecem sujeitos a seus respectivos direitos."),
                ("Mudanças antes do lançamento comercial", "As informações finais da entidade, dados de contato, lei aplicável, termos de resolução de disputas e divulgações comerciais serão adicionados antes da ativação de qualquer serviço pago ou programa de parceiros verificado."),
            ),
        ),
    },
    "es": {
        "/privacy": LegalPage(
            "Privacidad — PrediBeacon",
            (("/", "PrediBeacon"), ("/terms", "Términos"), ("/methodology", "Metodología")),
            "Aviso de privacidad previo al lanzamiento",
            "Este aviso describe el servicio público actual. Se actualizará antes de habilitar cuentas, analítica, atribución publicitaria o enlaces comerciales.",
            (
                ("Uso público actual", "PrediBeacon no ofrece actualmente cuentas públicas de usuario, depósitos, operaciones, boletines ni seguimiento de afiliados. La aplicación no instala intencionalmente cookies publicitarias o de analítica. Cuando un visitante elige un enlace a una plataforma externa, PrediBeacon registra un identificador de clic propio, el mercado, el contexto de campaña cuando existe, la página de referencia y la plataforma de destino para seguridad, medición de rendimiento y futura conciliación con socios. No registra una operación ni un depósito."),
                ("Registros técnicos", "Los proveedores de alojamiento y seguridad pueden procesar datos ordinarios de las solicitudes, como dirección IP, marca de tiempo, ruta solicitada, agente de usuario e información de errores, para prestar y proteger el servicio."),
                ("Acceso administrativo", "La interfaz editorial privada conserva su token únicamente en la memoria de la pestaña actual del navegador y no usa almacenamiento local, almacenamiento de sesión ni cookies de autenticación. Las acciones administrativas quedan auditadas en la base de datos del servicio."),
                ("Fuentes externas", "Al abrir un enlace a una fuente o plataforma, el visitante accede a un tercero sujeto a sus propias condiciones de privacidad. PrediBeacon no controla esos servicios."),
                ("Cambios futuros", "Antes de habilitar boletines, publicidad personalizada, atribución remunerada por socios o cuentas, PrediBeacon documentará la finalidad, base jurídica, conservación, encargados, transferencias internacionales y derechos de los usuarios."),
                ("Menores", "El servicio no está diseñado para incentivar a menores a participar en mercados de predicción. Las futuras funciones comerciales exigirán controles adecuados de edad y jurisdicción."),
            ),
        ),
        "/terms": LegalPage(
            "Términos — PrediBeacon",
            (("/", "PrediBeacon"), ("/privacy", "Privacidad"), ("/risk", "Divulgación de riesgos")),
            "Términos previos al lanzamiento para uso informativo",
            "Estos términos previos al lanzamiento no son los términos comerciales definitivos. Actualmente no se ofrecen servicios de pago, cuentas de usuario, ejecución de operaciones ni depósitos. Los enlaces orgánicos a plataformas externas pueden medirse, pero no se presenta ninguna asociación remunerada sin verificación.",
            (
                ("Finalidad informativa", "PrediBeacon agrega y explica información pública de mercados de predicción. Nada en el servicio constituye una oferta, solicitud, recomendación o garantía."),
                ("Sin custodia ni ejecución", "PrediBeacon no acepta ni custodia dinero de usuarios, no crea cuentas en plataformas, no envía órdenes ni liquida contratos."),
                ("Elegibilidad", "El acceso a la información no determina la elegibilidad para usar ninguna plataforma de terceros. Los usuarios son responsables de los requisitos de edad, identidad, ubicación y legislación aplicable."),
                ("Exactitud y disponibilidad", "Los datos pueden estar retrasados, incompletos o ser corregidos. El servicio puede modificar, suspender o retirar contenido para resolver errores, problemas de seguridad o actualizaciones de las fuentes."),
                ("Servicios de terceros", "Los nombres y enlaces de terceros identifican fuentes o plataformas y no implican propiedad, respaldo ni asociación. Se aplican sus términos independientes."),
                ("Uso aceptable", "Los usuarios no deben atacar el servicio, eludir controles de acceso, extraer datos de forma perjudicial, tergiversar contenido, manipular mercados ni usar PrediBeacon para infringir la ley o derechos de terceros."),
                ("Propiedad intelectual", "La marca PrediBeacon, las explicaciones originales y el software permanecen protegidos. Los hechos de las fuentes y las marcas de terceros siguen sujetos a sus respectivos derechos."),
                ("Cambios antes del lanzamiento comercial", "La información final de la entidad, los datos de contacto, la ley aplicable, las condiciones de resolución de disputas y las divulgaciones comerciales se añadirán antes de activar cualquier servicio de pago o programa de socios verificado."),
            ),
        ),
    },
    "fr": {
        "/privacy": LegalPage(
            "Confidentialité — PrediBeacon",
            (("/", "PrediBeacon"), ("/terms", "Conditions"), ("/methodology", "Méthodologie")),
            "Avis de confidentialité avant lancement",
            "Le présent avis décrit le service public actuel. Il sera mis à jour avant l’activation de comptes, de mesures d’audience, d’attribution publicitaire ou de liens commerciaux.",
            (
                ("Utilisation publique actuelle", "PrediBeacon ne propose actuellement ni comptes utilisateurs publics, ni dépôts, ni exécution d’opérations, ni newsletters, ni suivi d’affiliation. L’application ne dépose pas intentionnellement de cookies publicitaires ou de mesure d’audience. Lorsqu’un visiteur choisit un lien vers une plateforme externe, PrediBeacon enregistre un identifiant de clic interne, le marché, le contexte de campagne lorsqu’il existe, la page de provenance et la plateforme de destination à des fins de sécurité, de mesure des performances et de future réconciliation avec des partenaires. PrediBeacon n’enregistre ni opération ni dépôt."),
                ("Données techniques", "Les prestataires d’hébergement et de sécurité peuvent traiter des données ordinaires de requête telles que l’adresse IP, l’horodatage, le chemin demandé, l’agent utilisateur et les informations d’erreur afin de fournir et protéger le service."),
                ("Accès administratif", "L’interface éditoriale privée conserve son jeton uniquement dans la mémoire de l’onglet courant du navigateur et n’utilise ni stockage local, ni stockage de session, ni cookie d’authentification. Les actions administratives sont consignées dans la base de données du service."),
                ("Sources externes", "L’ouverture d’un lien vers une source ou une plateforme dirige le visiteur vers un tiers régi par ses propres règles de confidentialité. PrediBeacon ne contrôle pas ces services."),
                ("Évolutions futures", "Avant d’activer des newsletters, de la publicité personnalisée, une attribution rémunérée par des partenaires ou des comptes, PrediBeacon documentera la finalité, la base juridique, la durée de conservation, les sous-traitants, les transferts internationaux et les droits des utilisateurs."),
                ("Mineurs", "Le service n’est pas conçu pour encourager les mineurs à participer aux marchés de prédiction. Les futures fonctionnalités commerciales exigeront des contrôles adaptés d’âge et de juridiction."),
            ),
        ),
        "/terms": LegalPage(
            "Conditions — PrediBeacon",
            (("/", "PrediBeacon"), ("/privacy", "Confidentialité"), ("/risk", "Divulgation des risques")),
            "Conditions d’utilisation informative avant lancement",
            "Ces conditions avant lancement ne constituent pas les conditions commerciales définitives. Aucun service payant, compte utilisateur, exécution d’opération ou dépôt n’est actuellement proposé. Les liens organiques vers des plateformes externes peuvent être mesurés, mais aucun partenariat rémunéré n’est présenté sans vérification.",
            (
                ("Finalité informative", "PrediBeacon agrège et explique des informations publiques sur les marchés de prédiction. Aucun élément du service ne constitue une offre, une sollicitation, une recommandation ou une garantie."),
                ("Aucune conservation de fonds ni exécution", "PrediBeacon n’accepte ni ne conserve l’argent des utilisateurs, ne crée pas de comptes auprès des plateformes, ne passe pas d’ordres et ne règle pas de contrats."),
                ("Éligibilité", "L’accès aux informations ne détermine pas l’éligibilité à utiliser une plateforme tierce. Les utilisateurs sont responsables des exigences d’âge, d’identité, de localisation et de droit applicable."),
                ("Exactitude et disponibilité", "Les données peuvent être retardées, incomplètes ou corrigées. Le service peut modifier, suspendre ou retirer du contenu afin de traiter des erreurs, des questions de sécurité ou des mises à jour des sources."),
                ("Services tiers", "Les noms et liens de tiers identifient des sources ou plateformes et n’impliquent ni propriété, ni approbation, ni partenariat. Leurs conditions distinctes s’appliquent."),
                ("Utilisation acceptable", "Les utilisateurs ne doivent pas attaquer le service, contourner les contrôles d’accès, extraire des données de manière nuisible, déformer le contenu, manipuler les marchés ou utiliser PrediBeacon pour violer la loi ou les droits de tiers."),
                ("Propriété intellectuelle", "La marque PrediBeacon, les explications originales et le logiciel restent protégés. Les faits provenant des sources et les marques de tiers restent soumis à leurs droits respectifs."),
                ("Modifications avant le lancement commercial", "Les informations définitives sur l’entité, les coordonnées, le droit applicable, les modalités de règlement des litiges et les informations commerciales seront ajoutées avant l’activation de tout service payant ou programme partenaire vérifié."),
            ),
        ),
    },
    "de": {
        "/privacy": LegalPage(
            "Datenschutz — PrediBeacon",
            (("/", "PrediBeacon"), ("/terms", "Bedingungen"), ("/methodology", "Methodik")),
            "Datenschutzhinweis vor dem Start",
            "Dieser Hinweis beschreibt den derzeitigen öffentlichen Dienst. Er wird aktualisiert, bevor Konten, Analysen, Werbezuordnung oder kommerzielle Links aktiviert werden.",
            (
                ("Derzeitige öffentliche Nutzung", "PrediBeacon bietet derzeit keine öffentlichen Benutzerkonten, Einzahlungen, Handelsausführung, Newsletter oder Affiliate-Nachverfolgung an. Die Anwendung setzt absichtlich keine Werbe- oder Analyse-Cookies. Wenn ein Besucher einen Link zu einer externen Plattform auswählt, erfasst PrediBeacon eine eigene Klick-ID, den Markt, gegebenenfalls den Kampagnenkontext, die verweisende Seite und die Zielplattform für Sicherheit, Leistungsmessung und künftige Partnerabstimmung. Ein Handel oder eine Einzahlung wird nicht erfasst."),
                ("Technische Aufzeichnungen", "Hosting- und Sicherheitsanbieter können übliche Anfragedaten wie IP-Adresse, Zeitstempel, angeforderten Pfad, User-Agent und Fehlerinformationen verarbeiten, um den Dienst bereitzustellen und zu schützen."),
                ("Administrativer Zugriff", "Die private redaktionelle Oberfläche hält ihr Token nur im Speicher des aktuellen Browser-Tabs und verwendet weder lokalen Speicher noch Sitzungsspeicher oder Authentifizierungs-Cookies. Administrative Aktionen werden in der Dienstdatenbank protokolliert."),
                ("Externe Quellen", "Das Öffnen eines Quellen- oder Plattformlinks führt den Besucher zu einem Dritten, für den dessen eigene Datenschutzbedingungen gelten. PrediBeacon kontrolliert diese Dienste nicht."),
                ("Künftige Änderungen", "Vor der Aktivierung von Newslettern, personalisierter Werbung, vergüteter Partnerzuordnung oder Konten dokumentiert PrediBeacon Zweck, Rechtsgrundlage, Aufbewahrung, Auftragsverarbeiter, internationale Übermittlungen und Nutzerrechte."),
                ("Minderjährige", "Der Dienst ist nicht darauf ausgelegt, Minderjährige zur Teilnahme an Prognosemärkten zu ermutigen. Künftige kommerzielle Funktionen erfordern angemessene Alters- und Jurisdiktionskontrollen."),
            ),
        ),
        "/terms": LegalPage(
            "Bedingungen — PrediBeacon",
            (("/", "PrediBeacon"), ("/privacy", "Datenschutz"), ("/risk", "Risikohinweis")),
            "Vorläufige Bedingungen für die informative Nutzung",
            "Diese Bedingungen vor dem Start sind nicht die endgültigen Geschäftsbedingungen. Derzeit werden kein kostenpflichtiger Dienst, kein Benutzerkonto, keine Handelsausführung und keine Einzahlung angeboten. Organische Links zu externen Plattformen können gemessen werden, aber eine bezahlte Partnerschaft wird ohne Verifizierung nicht dargestellt.",
            (
                ("Informationszweck", "PrediBeacon bündelt und erläutert öffentliche Informationen zu Prognosemärkten. Nichts im Dienst stellt ein Angebot, eine Aufforderung, eine Empfehlung oder eine Garantie dar."),
                ("Keine Verwahrung oder Ausführung", "PrediBeacon nimmt kein Nutzergeld an oder verwahrt es, erstellt keine Plattformkonten, erteilt keine Aufträge und wickelt keine Verträge ab."),
                ("Berechtigung", "Der Zugang zu Informationen begründet keine Berechtigung zur Nutzung einer Plattform eines Dritten. Nutzer sind selbst für Anforderungen an Alter, Identität, Standort und anwendbares Recht verantwortlich."),
                ("Genauigkeit und Verfügbarkeit", "Daten können verzögert, unvollständig oder korrigiert sein. Der Dienst kann Inhalte ändern, aussetzen oder entfernen, um Fehler, Sicherheitsfragen oder Aktualisierungen der Quellen zu berücksichtigen."),
                ("Dienste Dritter", "Namen und Links Dritter kennzeichnen Quellen oder Plattformen und bedeuten weder Eigentum noch Billigung oder Partnerschaft. Es gelten deren gesonderte Bedingungen."),
                ("Zulässige Nutzung", "Nutzer dürfen den Dienst nicht angreifen, Zugangskontrollen umgehen, Daten auf schädliche Weise automatisiert erfassen, Inhalte falsch darstellen, Märkte manipulieren oder PrediBeacon zur Verletzung von Gesetzen oder Rechten Dritter verwenden."),
                ("Geistiges Eigentum", "Die Marke PrediBeacon, ursprüngliche Erläuterungen und die Software bleiben geschützt. Fakten aus Quellen und Marken Dritter unterliegen ihren jeweiligen Rechten."),
                ("Änderungen vor dem kommerziellen Start", "Endgültige Angaben zur Rechtseinheit, Kontaktdaten, anwendbares Recht, Streitbeilegungsbedingungen und kommerzielle Offenlegungen werden vor der Aktivierung eines kostenpflichtigen Dienstes oder eines verifizierten Partnerprogramms ergänzt."),
            ),
        ),
    },
    "it": {
        "/privacy": LegalPage(
            "Privacy — PrediBeacon",
            (("/", "PrediBeacon"), ("/terms", "Termini"), ("/methodology", "Metodologia")),
            "Informativa sulla privacy pre-lancio",
            "Questa informativa descrive l’attuale servizio pubblico. Sarà aggiornata prima di abilitare account, analisi, attribuzione pubblicitaria o link commerciali.",
            (
                ("Uso pubblico attuale", "PrediBeacon attualmente non offre account utente pubblici, depositi, esecuzione di operazioni, newsletter o tracciamento di affiliazione. L’applicazione non imposta intenzionalmente cookie pubblicitari o di analisi. Quando un visitatore sceglie un link verso una piattaforma esterna, PrediBeacon registra un identificatore di clic proprietario, il mercato, il contesto della campagna quando presente, la pagina di provenienza e la piattaforma di destinazione per sicurezza, misurazione delle prestazioni e futura riconciliazione con partner. Non registra un’operazione o un deposito."),
                ("Registri tecnici", "I fornitori di hosting e sicurezza possono trattare normali dati di richiesta, come indirizzo IP, data e ora, percorso richiesto, user agent e informazioni sugli errori, per fornire e proteggere il servizio."),
                ("Accesso amministrativo", "L’interfaccia editoriale privata conserva il proprio token solo nella memoria della scheda corrente del browser e non utilizza local storage, session storage o cookie di autenticazione. Le azioni amministrative sono registrate nel database del servizio."),
                ("Fonti esterne", "L’apertura di un link a una fonte o piattaforma porta il visitatore a un soggetto terzo regolato dalla propria informativa sulla privacy. PrediBeacon non controlla tali servizi."),
                ("Modifiche future", "Prima di abilitare newsletter, pubblicità personalizzata, attribuzione remunerata da partner o account, PrediBeacon documenterà finalità, base giuridica, conservazione, responsabili del trattamento, trasferimenti internazionali e diritti degli utenti."),
                ("Minori", "Il servizio non è progettato per incoraggiare i minori a partecipare ai mercati di previsione. Le future funzionalità commerciali richiederanno controlli adeguati di età e giurisdizione."),
            ),
        ),
        "/terms": LegalPage(
            "Termini — PrediBeacon",
            (("/", "PrediBeacon"), ("/privacy", "Privacy"), ("/risk", "Informativa sui rischi")),
            "Termini pre-lancio per uso informativo",
            "Questi termini pre-lancio non sono i termini commerciali definitivi. Attualmente non sono offerti servizi a pagamento, account utente, esecuzione di operazioni o depositi. I link organici verso piattaforme esterne possono essere misurati, ma nessuna partnership retribuita viene rappresentata senza verifica.",
            (
                ("Finalità informativa", "PrediBeacon aggrega e spiega informazioni pubbliche sui mercati di previsione. Nulla nel servizio costituisce un’offerta, una sollecitazione, una raccomandazione o una garanzia."),
                ("Nessuna custodia o esecuzione", "PrediBeacon non accetta né custodisce denaro degli utenti, non crea account sulle piattaforme, non inoltra ordini e non regola contratti."),
                ("Idoneità", "L’accesso alle informazioni non determina l’idoneità a utilizzare una piattaforma di terzi. Gli utenti sono responsabili dei requisiti relativi a età, identità, ubicazione e legge applicabile."),
                ("Accuratezza e disponibilità", "I dati possono essere in ritardo, incompleti o corretti. Il servizio può modificare, sospendere o rimuovere contenuti per gestire errori, problemi di sicurezza o aggiornamenti delle fonti."),
                ("Servizi di terzi", "Nomi e link di terzi identificano fonti o piattaforme e non implicano proprietà, approvazione o partnership. Si applicano i loro termini separati."),
                ("Uso accettabile", "Gli utenti non devono attaccare il servizio, aggirare i controlli di accesso, estrarre dati in modo dannoso, travisare contenuti, manipolare mercati o utilizzare PrediBeacon per violare la legge o i diritti di terzi."),
                ("Proprietà intellettuale", "Il marchio PrediBeacon, le spiegazioni originali e il software restano protetti. I fatti delle fonti e i marchi di terzi restano soggetti ai rispettivi diritti."),
                ("Modifiche prima del lancio commerciale", "Le informazioni definitive sull’entità, i recapiti, la legge applicabile, le condizioni per la risoluzione delle controversie e le comunicazioni commerciali saranno aggiunte prima dell’attivazione di qualsiasi servizio a pagamento o programma partner verificato."),
            ),
        ),
    },
    "ja": {
        "/privacy": LegalPage(
            "プライバシー — PrediBeacon",
            (("/", "PrediBeacon"), ("/terms", "利用規約"), ("/methodology", "方法論")),
            "公開前プライバシー通知",
            "本通知は現在の公開サービスについて説明するものです。アカウント、アクセス解析、広告のアトリビューション、または商用リンクを有効にする前に更新されます。",
            (
                ("現在の公開利用", "PrediBeacon は現在、一般向けユーザーアカウント、入金、取引執行、ニュースレター、またはアフィリエイト追跡を提供していません。アプリケーションは広告またはアクセス解析用 Cookie を意図的に設定しません。訪問者が外部プラットフォームへのリンクを選択した場合、PrediBeacon はセキュリティ、性能測定、将来のパートナー照合のため、ファーストパーティのクリック識別子、市場、存在する場合はキャンペーン情報、参照元ページ、および移動先プラットフォームを記録します。取引や入金は記録しません。"),
                ("技術記録", "ホスティングおよびセキュリティ事業者は、サービスの提供と保護のため、IP アドレス、日時、要求されたパス、ユーザーエージェント、エラー情報などの通常のリクエストデータを処理する場合があります。"),
                ("管理者アクセス", "非公開の編集インターフェースは、トークンを現在のブラウザータブのメモリ内だけに保持し、ローカルストレージ、セッションストレージ、認証 Cookie を使用しません。管理操作はサービスのデータベースに監査記録として保存されます。"),
                ("外部ソース", "ソースまたはプラットフォームへのリンクを開くと、訪問者は独自のプライバシー条件が適用される第三者サービスへ移動します。PrediBeacon はそれらのサービスを管理しません。"),
                ("今後の変更", "ニュースレター、パーソナライズ広告、パートナーによる有償アトリビューション、またはアカウントを有効にする前に、PrediBeacon は目的、法的根拠、保存期間、処理者、国際移転、ユーザーの権利を文書化します。"),
                ("未成年者", "本サービスは未成年者に予測市場への参加を促すことを目的としていません。将来の商用機能には、適切な年齢および法域の管理が必要です。"),
            ),
        ),
        "/terms": LegalPage(
            "利用規約 — PrediBeacon",
            (("/", "PrediBeacon"), ("/privacy", "プライバシー"), ("/risk", "リスク開示")),
            "情報利用に関する公開前利用規約",
            "本公開前規約は最終的な商用利用規約ではありません。現在、有料サービス、ユーザーアカウント、取引執行、入金は提供されていません。外部プラットフォームへのオーガニックリンクは測定される場合がありますが、検証なしに有償パートナーシップを示すことはありません。",
            (
                ("情報提供の目的", "PrediBeacon は予測市場に関する公開情報を集約し、説明します。本サービス上の情報は、申込み、勧誘、推奨、または保証ではありません。"),
                ("資金保管・取引執行なし", "PrediBeacon はユーザー資金を受領または保管せず、プラットフォームのアカウントを作成せず、注文を出さず、契約を決済しません。"),
                ("利用資格", "情報へのアクセスによって、第三者プラットフォームを利用する資格が認められるわけではありません。年齢、本人確認、所在地、適用法に関する要件はユーザー自身の責任です。"),
                ("正確性と可用性", "データは遅延、不完全、または訂正される場合があります。本サービスは、誤り、安全上の問題、情報源の更新に対応するため、内容を変更、一時停止、または削除する場合があります。"),
                ("第三者サービス", "第三者の名称やリンクは情報源またはプラットフォームを示すためのものであり、所有、推奨、提携を意味しません。それぞれの第三者の規約が適用されます。"),
                ("許容される利用", "ユーザーは、本サービスへの攻撃、アクセス制御の回避、有害な方法でのスクレイピング、内容の虚偽表示、市場操作、または法令・第三者の権利を侵害する目的で PrediBeacon を利用してはなりません。"),
                ("知的財産", "PrediBeacon のブランド、独自の説明、ソフトウェアは保護されています。情報源の事実および第三者の商標は、それぞれの権利に従います。"),
                ("商用開始前の変更", "有料サービスまたは検証済みパートナープログラムを有効にする前に、最終的な法人情報、連絡先、準拠法、紛争解決条件、商用開示を追加します。"),
            ),
        ),
    },
    "ko": {
        "/privacy": LegalPage(
            "개인정보 — PrediBeacon",
            (("/", "PrediBeacon"), ("/terms", "이용약관"), ("/methodology", "방법론")),
            "출시 전 개인정보 안내",
            "이 안내는 현재 공개 서비스를 설명합니다. 계정, 분석, 광고 기여도 측정 또는 상업용 링크를 활성화하기 전에 업데이트됩니다.",
            (
                ("현재 공개 이용", "PrediBeacon은 현재 공개 사용자 계정, 입금, 거래 실행, 뉴스레터 또는 제휴 추적을 제공하지 않습니다. 애플리케이션은 광고 또는 분석 쿠키를 의도적으로 설정하지 않습니다. 방문자가 외부 플랫폼 링크를 선택하면 PrediBeacon은 보안, 성능 측정 및 향후 파트너 정산을 위해 자사 클릭 식별자, 시장, 존재하는 경우 캠페인 정보, 유입 페이지 및 대상 플랫폼을 기록합니다. 거래나 입금은 기록하지 않습니다."),
                ("기술 기록", "호스팅 및 보안 제공업체는 서비스를 제공하고 보호하기 위해 IP 주소, 시간, 요청 경로, 사용자 에이전트 및 오류 정보와 같은 일반적인 요청 데이터를 처리할 수 있습니다."),
                ("관리자 접근", "비공개 편집 인터페이스는 토큰을 현재 브라우저 탭의 메모리에만 보관하며 로컬 스토리지, 세션 스토리지 또는 인증 쿠키를 사용하지 않습니다. 관리자 작업은 서비스 데이터베이스에 감사 기록으로 남습니다."),
                ("외부 출처", "출처 또는 플랫폼 링크를 열면 방문자는 해당 제3자의 개인정보 조건이 적용되는 서비스로 이동합니다. PrediBeacon은 이러한 서비스를 통제하지 않습니다."),
                ("향후 변경", "뉴스레터, 개인 맞춤 광고, 유료 파트너 기여도 측정 또는 계정을 활성화하기 전에 PrediBeacon은 목적, 법적 근거, 보관 기간, 처리자, 국제 이전 및 사용자 권리를 문서화합니다."),
                ("미성년자", "이 서비스는 미성년자의 예측시장 참여를 장려하도록 설계되지 않았습니다. 향후 상업 기능에는 적절한 연령 및 관할지역 통제가 필요합니다."),
            ),
        ),
        "/terms": LegalPage(
            "이용약관 — PrediBeacon",
            (("/", "PrediBeacon"), ("/privacy", "개인정보"), ("/risk", "위험 고지")),
            "정보 이용을 위한 출시 전 약관",
            "이 출시 전 약관은 최종 상업 약관이 아닙니다. 현재 유료 서비스, 사용자 계정, 거래 실행 또는 입금은 제공되지 않습니다. 외부 플랫폼으로 연결되는 자연 링크는 측정될 수 있지만 검증 없이 유료 파트너십을 표시하지 않습니다.",
            (
                ("정보 제공 목적", "PrediBeacon은 예측시장에 관한 공개 정보를 집계하고 설명합니다. 서비스의 어떠한 내용도 제안, 권유, 추천 또는 보증이 아닙니다."),
                ("자금 보관 또는 실행 없음", "PrediBeacon은 사용자 자금을 받거나 보관하지 않으며 플랫폼 계정을 만들거나 주문을 제출하거나 계약을 결제하지 않습니다."),
                ("이용 자격", "정보에 접근하는 것만으로 제3자 플랫폼을 이용할 자격이 성립하지 않습니다. 연령, 신원, 위치 및 적용 법률 요건은 사용자의 책임입니다."),
                ("정확성과 이용 가능성", "데이터는 지연되거나 불완전하거나 수정될 수 있습니다. 서비스는 오류, 안전 문제 또는 출처 업데이트에 대응하기 위해 콘텐츠를 변경, 중단 또는 삭제할 수 있습니다."),
                ("제3자 서비스", "제3자의 이름과 링크는 출처 또는 플랫폼을 식별하기 위한 것이며 소유, 보증 또는 파트너십을 의미하지 않습니다. 해당 제3자의 별도 약관이 적용됩니다."),
                ("허용되는 이용", "사용자는 서비스를 공격하거나 접근 통제를 우회하거나 유해한 방식으로 데이터를 수집하거나 콘텐츠를 왜곡하거나 시장을 조작하거나 법률 또는 제3자 권리를 침해하기 위해 PrediBeacon을 사용해서는 안 됩니다."),
                ("지식재산권", "PrediBeacon 브랜드, 독창적인 설명 및 소프트웨어는 보호됩니다. 출처의 사실과 제3자 상표는 각 권리의 적용을 받습니다."),
                ("상업 출시 전 변경", "유료 서비스 또는 검증된 파트너 프로그램을 활성화하기 전에 최종 법인 정보, 연락처, 준거법, 분쟁 해결 조건 및 상업적 공시가 추가됩니다."),
            ),
        ),
    },
    "zh-CN": {
        "/privacy": LegalPage(
            "隐私 — PrediBeacon",
            (("/", "PrediBeacon"), ("/terms", "条款"), ("/methodology", "方法论")),
            "上线前隐私声明",
            "本声明说明当前的公开服务。在启用账户、分析、广告归因或商业链接之前，本声明将会更新。",
            (
                ("当前公开使用", "PrediBeacon 目前不提供公开用户账户、存款、交易执行、新闻通讯或联盟跟踪。应用程序不会有意设置广告或分析 Cookie。当访客选择外部平台链接时，PrediBeacon 会出于安全、性能衡量和未来合作伙伴对账的目的，记录第一方点击标识符、市场、存在时的活动上下文、来源页面和目标平台。PrediBeacon 不记录交易或存款。"),
                ("技术记录", "托管和安全服务商可能会处理普通请求数据，例如 IP 地址、时间戳、请求路径、用户代理和错误信息，以提供并保护本服务。"),
                ("管理访问", "私有编辑界面仅在当前浏览器标签页的内存中保存其令牌，不使用本地存储、会话存储或身份验证 Cookie。管理操作会记录在服务数据库中以供审计。"),
                ("外部来源", "打开来源或平台链接会将访客带到受其自身隐私条款约束的第三方服务。PrediBeacon 不控制这些服务。"),
                ("未来变更", "在启用新闻通讯、个性化广告、合作伙伴付费归因或账户之前，PrediBeacon 将记录处理目的、法律依据、保留期限、处理方、国际传输和用户权利。"),
                ("未成年人", "本服务并非旨在鼓励未成年人参与预测市场。未来的商业功能将要求适当的年龄和司法辖区控制。"),
            ),
        ),
        "/terms": LegalPage(
            "条款 — PrediBeacon",
            (("/", "PrediBeacon"), ("/privacy", "隐私"), ("/risk", "风险披露")),
            "用于信息服务的上线前条款",
            "这些上线前条款不是最终商业条款。目前不提供付费服务、用户账户、交易执行或存款。前往外部平台的自然链接可能会被衡量，但未经验证不会表示存在付费合作关系。",
            (
                ("信息用途", "PrediBeacon 汇总并解释公开的预测市场信息。服务中的任何内容都不构成要约、招揽、推荐或保证。"),
                ("不托管资金或执行交易", "PrediBeacon 不接受或保管用户资金，不创建平台账户，不提交订单，也不结算合约。"),
                ("资格", "访问信息并不意味着有资格使用任何第三方平台。用户自行负责年龄、身份、所在地和适用法律要求。"),
                ("准确性和可用性", "数据可能延迟、不完整或被更正。为处理错误、安全问题或来源更新，本服务可能更改、暂停或删除内容。"),
                ("第三方服务", "第三方名称和链接仅用于识别来源或平台，并不表示所有权、认可或合作关系。适用其各自独立的条款。"),
                ("可接受的使用", "用户不得攻击服务、绕过访问控制、以有害方式抓取数据、歪曲内容、操纵市场，也不得使用 PrediBeacon 违反法律或第三方权利。"),
                ("知识产权", "PrediBeacon 品牌、原创说明和软件受到保护。来源事实和第三方商标仍受其各自权利约束。"),
                ("商业上线前的变更", "在启用任何付费服务或经验证的合作伙伴计划之前，将补充最终实体信息、联系方式、适用法律、争议解决条款和商业披露。"),
            ),
        ),
    },
    "ar": {
        "/privacy": LegalPage(
            "الخصوصية — PrediBeacon",
            (("/", "PrediBeacon"), ("/terms", "الشروط"), ("/methodology", "المنهجية")),
            "إشعار الخصوصية قبل الإطلاق",
            "يصف هذا الإشعار الخدمة العامة الحالية. وسيتم تحديثه قبل تفعيل الحسابات أو التحليلات أو إسناد الإعلانات أو الروابط التجارية.",
            (
                ("الاستخدام العام الحالي", "لا تقدم PrediBeacon حاليًا حسابات مستخدمين عامة أو إيداعات أو تنفيذ صفقات أو نشرات إخبارية أو تتبعًا للتسويق بالعمولة. ولا يضع التطبيق عمدًا ملفات تعريف ارتباط للإعلانات أو التحليلات. عندما يختار الزائر رابطًا إلى منصة خارجية، تسجل PrediBeacon معرّف نقرة من الطرف الأول والسوق وسياق الحملة عند وجوده والصفحة المُحيلة والمنصة الوجهة لأغراض الأمان وقياس الأداء والتسوية المستقبلية مع الشركاء. ولا تسجل صفقة أو إيداعًا."),
                ("السجلات التقنية", "قد يعالج مزودو الاستضافة والأمان بيانات الطلب المعتادة مثل عنوان IP والطابع الزمني والمسار المطلوب ووكيل المستخدم ومعلومات الأخطاء لتقديم الخدمة وحمايتها."),
                ("الوصول الإداري", "تحتفظ واجهة التحرير الخاصة برمزها فقط في ذاكرة علامة تبويب المتصفح الحالية ولا تستخدم التخزين المحلي أو تخزين الجلسة أو ملف تعريف ارتباط للمصادقة. ويتم تدقيق الإجراءات الإدارية في قاعدة بيانات الخدمة."),
                ("المصادر الخارجية", "يؤدي فتح رابط مصدر أو منصة إلى انتقال الزائر إلى طرف ثالث تحكمه شروط الخصوصية الخاصة به. ولا تتحكم PrediBeacon في تلك الخدمات."),
                ("التغييرات المستقبلية", "قبل تفعيل النشرات الإخبارية أو الإعلانات المخصصة أو الإسناد المدفوع من الشركاء أو الحسابات، ستوثق PrediBeacon الغرض والأساس القانوني والاحتفاظ بالبيانات والمعالجين والتحويلات الدولية وحقوق المستخدمين."),
                ("القاصرون", "لم تُصمم الخدمة لتشجيع القاصرين على المشاركة في أسواق التوقعات. وستتطلب الميزات التجارية المستقبلية ضوابط مناسبة للعمر والاختصاص القضائي."),
            ),
        ),
        "/terms": LegalPage(
            "الشروط — PrediBeacon",
            (("/", "PrediBeacon"), ("/privacy", "الخصوصية"), ("/risk", "إفصاح المخاطر")),
            "شروط الاستخدام المعلوماتي قبل الإطلاق",
            "هذه الشروط السابقة للإطلاق ليست الشروط التجارية النهائية. لا يتم حاليًا تقديم خدمة مدفوعة أو حساب مستخدم أو تنفيذ صفقات أو إيداعات. وقد تُقاس الروابط العضوية إلى المنصات الخارجية، لكن لا يتم تمثيل أي شراكة مدفوعة دون تحقق.",
            (
                ("الغرض المعلوماتي", "تجمع PrediBeacon معلومات عامة عن أسواق التوقعات وتشرحها. ولا يمثل أي شيء في الخدمة عرضًا أو دعوة أو توصية أو ضمانًا."),
                ("لا حفظ للأموال ولا تنفيذ", "لا تقبل PrediBeacon أموال المستخدمين ولا تحتفظ بها، ولا تنشئ حسابات على المنصات، ولا تقدم أوامر، ولا تسوي العقود."),
                ("الأهلية", "لا يثبت الوصول إلى المعلومات أهلية استخدام أي منصة تابعة لطرف ثالث. ويتحمل المستخدمون مسؤولية متطلبات العمر والهوية والموقع والقانون المعمول به."),
                ("الدقة والتوافر", "قد تكون البيانات متأخرة أو غير مكتملة أو خاضعة للتصحيح. وقد تغير الخدمة المحتوى أو تعلقه أو تزيله لمعالجة الأخطاء أو مخاوف السلامة أو تحديثات المصادر."),
                ("خدمات الأطراف الثالثة", "تحدد أسماء وروابط الأطراف الثالثة المصادر أو المنصات ولا تعني الملكية أو التأييد أو الشراكة. وتطبق شروطها المنفصلة."),
                ("الاستخدام المقبول", "يجب ألا يهاجم المستخدمون الخدمة أو يتجاوزوا ضوابط الوصول أو يجمعوا البيانات بطريقة ضارة أو يحرفوا المحتوى أو يتلاعبوا بالأسواق أو يستخدموا PrediBeacon لانتهاك القانون أو حقوق الأطراف الثالثة."),
                ("الملكية الفكرية", "تظل علامة PrediBeacon والشروحات الأصلية والبرمجيات محمية. وتظل حقائق المصادر وعلامات الأطراف الثالثة خاضعة لحقوق أصحابها."),
                ("التغييرات قبل الإطلاق التجاري", "ستتم إضافة معلومات الكيان النهائية وبيانات الاتصال والقانون الحاكم وشروط تسوية المنازعات والإفصاحات التجارية قبل تفعيل أي خدمة مدفوعة أو برنامج شراكة موثق."),
            ),
        ),
    },
}


def _render(page: LegalPage) -> str:
    nav = "".join(f'<a href="{escape(href, quote=True)}">{escape(label)}</a>' for href, label in page.nav)
    sections = "".join(f"<h2>{escape(title)}</h2><p>{escape(body)}</p>" for title, body in page.sections)
    return f'<main class="wrap"><nav>{nav}</nav><h1>{escape(page.heading)}</h1><p class="note">{escape(page.notice)}</p>{sections}</main>'


def translate_legal_page(path: str, html: str, locale: str) -> str:
    """Render complete visible Privacy/Terms copy for every supported non-English locale.

    English templates remain the canonical source. Translation affects presentation only;
    provider names and the PrediBeacon brand are preserved.
    """
    if locale == "en":
        return html
    page = PAGES.get(locale, {}).get(path)
    if page is None:
        return html
    start = html.find('<main class="wrap">')
    end = html.rfind("</main>")
    if start < 0 or end < start:
        return html
    translated = html[:start] + _render(page) + html[end + len("</main>"):]
    if "<title>" in translated and "</title>" in translated:
        title_start = translated.index("<title>") + len("<title>")
        title_end = translated.index("</title>", title_start)
        translated = translated[:title_start] + escape(page.title) + translated[title_end:]
    return translated
