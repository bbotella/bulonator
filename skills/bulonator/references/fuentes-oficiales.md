# Catálogo de fuentes oficiales y primarias

Pregunta guía: **¿quién tendría este dato si fuera cierto?** Ve a esa fuente antes que a la prensa.

Cómo buscar dentro de un dominio oficial:

- `WebSearch` con `allowed_domains` (por ejemplo `["boe.es"]` o `["ine.es"]`) y términos literales.
- `WebFetch` para abrir el documento. Pide al modelo "la cita literal exacta" del pasaje relevante.
- Para cifras y frases críticas, confírmalas sobre el documento original: `curl -sL <url> | grep -i "<fragmento>"`. Si es un PDF, descárgalo a `evidencias/docs/` y ábrelo con `Read`.
- Las herramientas de `scripts/bulonator.py` (`boe`, `ine`) y las API públicas que aparecen abajo dan datos estructurados sin intermediarios.

---

## España: normas y actos oficiales

| Fuente | Qué contiene | Acceso |
|---|---|---|
| **BOE**, Boletín Oficial del Estado | Leyes, reales decretos, órdenes, ayudas, nombramientos, convocatorias, BORME | <https://www.boe.es> · API abierta <https://www.boe.es/datosabiertos/> |
| BOE, legislación consolidada | Texto vigente de cada norma, con su historial de versiones | `python3 bulonator.py boe "<palabras del título>" [--desde AAAAMMDD]` |
| BOE, sumario diario | Todo lo publicado en un día | `python3 bulonator.py boe --sumario AAAAMMDD [palabras]` |
| Congreso de los Diputados | Iniciativas (proyectos y proposiciones de ley), diarios de sesiones, votaciones | <https://www.congreso.es> · datos abiertos <https://www.congreso.es/es/datos-abiertos> |
| Senado | Iniciativas, diarios de sesiones, enmiendas | <https://www.senado.es> |
| La Moncloa, referencias del Consejo de Ministros | Lo que aprueba el Gobierno cada semana. Ojo: un anteproyecto no es una ley | <https://www.lamoncloa.gob.es/consejodeministros/referencias/Paginas/index.aspx> |
| Poder Judicial, CENDOJ | Sentencias y autos de juzgados y tribunales | <https://www.poderjudicial.es/search/indexAN.jsp> |
| Tribunal Constitucional | Sentencias y recursos | <https://www.tribunalconstitucional.es> |
| Fiscalía General del Estado | Memorias anuales y circulares | <https://www.fiscal.es> |
| Portal de la Transparencia | Contratos, subvenciones, retribuciones de altos cargos | <https://transparencia.gob.es> |
| Base de Datos Nacional de Subvenciones | Quién recibe qué subvención pública | <https://www.infosubvenciones.es> |
| Junta Electoral Central | Acuerdos y normativa electoral | <https://www.juntaelectoralcentral.es> |
| Ministerio del Interior, Infoelectoral | Resultados electorales oficiales históricos | <https://infoelectoral.interior.gob.es> |

### Boletines autonómicos

Si la medida es autonómica, búscala en su boletín; si es municipal, en el boletín provincial (BOP).

| Comunidad | Boletín | Web |
|---|---|---|
| Andalucía | BOJA | <https://www.juntadeandalucia.es/eboja.html> |
| Aragón | BOA | <https://www.boa.aragon.es> |
| Asturias | BOPA | <https://sede.asturias.es/bopa> |
| Illes Balears | BOIB | <https://www.caib.es/eboibfront/> |
| Canarias | BOC | <https://www.gobiernodecanarias.org/boc/> |
| Cantabria | BOC | <https://boc.cantabria.es> |
| Castilla y León | BOCYL | <https://bocyl.jcyl.es> |
| Castilla-La Mancha | DOCM | <https://docm.jccm.es> |
| Cataluña | DOGC | <https://dogc.gencat.cat> |
| Comunitat Valenciana | DOGV | <https://dogv.gva.es> |
| Extremadura | DOE | <https://doe.juntaex.es> |
| Galicia | DOG | <https://www.xunta.gal/diario-oficial-galicia> |
| Comunidad de Madrid | BOCM | <https://www.bocm.es> |
| Región de Murcia | BORM | <https://www.borm.es> |
| Navarra | BON | <https://bon.navarra.es> |
| País Vasco | BOPV/EHAA | <https://www.euskadi.eus> (sección BOPV; para buscar, `WebSearch` con `allowed_domains: ["euskadi.eus"]` y "bopv") |
| La Rioja | BOR | <https://web.larioja.org/bor-portada> |
| Ceuta | BOCCE | <https://www.ceuta.es> |
| Melilla | BOME | <https://bomemelilla.es> |

## España: estadística oficial

| Fuente | Qué contiene | Acceso |
|---|---|---|
| **INE** | Población y Padrón, EPA (paro), IPC, migraciones, PIB, salarios, defunciones, vivienda | <https://www.ine.es> · API Tempus `https://servicios.ine.es/wstempus/js/ES/…` · `python3 bulonator.py ine "<tema>"`, luego `--tablas <COD>` y `--datos <ID>` |
| SEPE | Paro registrado y contratos. No es lo mismo que la tasa de paro de la EPA | <https://www.sepe.es/HomeSepe/que-es-el-sepe/estadisticas.html> |
| Seguridad Social | Afiliación, pensiones, prestaciones | <https://www.seg-social.es> |
| Ministerio del Interior | Balance de criminalidad, informes de inmigración irregular, seguridad vial | <https://www.interior.gob.es/opencms/es/prensa/balances-e-informes/> · portal estadístico <https://estadisticasdecriminalidad.ses.mir.es> |
| Agencia Tributaria | Estadísticas de IRPF, IVA, recaudación | <https://sede.agenciatributaria.gob.es/Sede/estadisticas.html> |
| Banco de España | Deuda, crédito, tipos, boletín estadístico | <https://www.bde.es> |
| AIReF | Previsiones fiscales y evaluación del gasto | <https://www.airef.es> |
| CIS | Barómetros y encuestas. Distingue la estimación de voto de la intención directa | <https://www.cis.es> |
| datos.gob.es | Catálogo nacional de datos abiertos | <https://datos.gob.es> |
| Idescat (Cataluña) | Estadística autonómica | <https://www.idescat.cat> |
| Eustat (País Vasco) | Estadística autonómica | <https://www.eustat.eus> |
| IGE (Galicia) | Estadística autonómica | <https://www.ige.gal> |
| ISTAC (Canarias) | Estadística autonómica | <https://www.gobiernodecanarias.org/istac/> |
| IECA (Andalucía) | Estadística autonómica | <https://www.juntadeandalucia.es/institutodeestadisticaycartografia> |

## España: salud, ciencia, medio ambiente y emergencias

| Fuente | Qué contiene | Acceso |
|---|---|---|
| Ministerio de Sanidad | Alertas, vacunación, datos sanitarios | <https://www.sanidad.gob.es> |
| AEMPS | Medicamentos autorizados, alertas y retiradas | <https://www.aemps.gob.es> · CIMA (API REST) `https://cima.aemps.es/cima/rest/medicamentos?nombre=<nombre>` |
| Instituto de Salud Carlos III | Vigilancia epidemiológica | <https://www.isciii.es> |
| AEMET | Datos meteorológicos y avisos. Útil para fechar imágenes por el tiempo que hacía | <https://www.aemet.es> · OpenData (clave gratuita) <https://opendata.aemet.es> |
| IGN | Terremotos, cartografía | <https://www.ign.es> |
| Protección Civil | Emergencias | <https://www.proteccioncivil.es> |
| DGT | Normas de tráfico, multas, estadísticas. Ojo con los timos que suplantan a la DGT | <https://www.dgt.es> |
| Red Eléctrica | Generación y demanda eléctrica | <https://www.ree.es/es/datos> |
| Policía Nacional | Comunicados y alertas de estafas | <https://www.policia.es> |
| Guardia Civil | Comunicados y alertas de estafas | <https://www.guardiacivil.es> |
| INCIBE | Alertas de fraude y phishing | <https://www.incibe.es> |

## Unión Europea

| Fuente | Qué contiene | Acceso |
|---|---|---|
| EUR-Lex | Legislación de la UE (Diario Oficial) | <https://eur-lex.europa.eu> |
| Eurostat | Estadísticas comparables de la UE | <https://ec.europa.eu/eurostat> · API `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/<dataset>?geo=ES&lang=ES` |
| Parlamento Europeo | Plenos, votaciones, textos aprobados | <https://www.europarl.europa.eu> · Observatorio Legislativo <https://oeil.secure.europarl.europa.eu> |
| Comisión Europea, sala de prensa | Comunicados y desmentidos oficiales | <https://ec.europa.eu/commission/presscorner/home/es> |
| Consejo de la UE | Decisiones y conclusiones | <https://www.consilium.europa.eu> |
| TJUE | Jurisprudencia | <https://curia.europa.eu> |
| EMA | Medicamentos y vacunas en la UE | <https://www.ema.europa.eu> |
| ECDC | Enfermedades transmisibles | <https://www.ecdc.europa.eu> |
| BCE | Política monetaria y datos | <https://www.ecb.europa.eu> · <https://data.ecb.europa.eu> |
| Frontex | Cruces irregulares de fronteras | <https://www.frontex.europa.eu> |
| Eurobarómetro | Encuestas de opinión de la UE | <https://europa.eu/eurobarometer> |

## Internacional

| Fuente | Qué contiene | Acceso |
|---|---|---|
| OMS | Salud global | <https://www.who.int> · <https://data.who.int> |
| ONU | Resoluciones y datos | <https://www.un.org> · <https://data.un.org> |
| ACNUR | Personas refugiadas | <https://www.unhcr.org/refugee-statistics/> |
| OIM, Missing Migrants | Migrantes muertos y desaparecidos | <https://missingmigrants.iom.int> |
| Banco Mundial | Indicadores por país | API `https://api.worldbank.org/v2/country/ES/indicator/<indicador>?format=json` |
| FMI | Datos macroeconómicos | <https://www.imf.org> |
| OCDE | Estadísticas comparadas | <https://data-explorer.oecd.org> |
| OIT | Empleo | <https://ilostat.ilo.org> |
| FAO | Alimentación y agricultura | <https://www.fao.org/faostat> |
| IPCC | Ciencia del clima | <https://www.ipcc.ch> |
| Copernicus | Clima y observación de la Tierra | <https://climate.copernicus.eu> |
| Our World in Data | Agregador secundario: cita siempre la fuente primaria que enlaza | <https://ourworldindata.org> |

## América Latina

| País | Diario oficial | Estadística |
|---|---|---|
| México | DOF <https://www.dof.gob.mx> | INEGI <https://www.inegi.org.mx> |
| Argentina | Boletín Oficial <https://www.boletinoficial.gob.ar> | INDEC <https://www.indec.gob.ar> |
| Colombia | Diario Oficial, Imprenta Nacional <https://www.imprenta.gov.co> | DANE <https://www.dane.gov.co> |
| Chile | Diario Oficial <https://www.diariooficial.interior.gob.cl> y LeyChile <https://www.bcn.cl/leychile> | INE <https://www.ine.gob.cl> |
| Perú | El Peruano <https://diariooficial.elperuano.pe> | INEI <https://www.inei.gob.pe> |
| Ecuador | Registro Oficial <https://www.registroficial.gob.ec> | INEC <https://www.ecuadorencifras.gob.ec> |
| Uruguay | IMPO <https://www.impo.com.uy> | INE <https://www.gub.uy/instituto-nacional-estadistica> |

## Otros países frecuentes

| País | Normas y parlamento | Estadística |
|---|---|---|
| Estados Unidos | Federal Register <https://www.federalregister.gov> · Congress.gov <https://www.congress.gov> | BLS <https://www.bls.gov> · Census <https://www.census.gov> · CDC <https://www.cdc.gov> |
| Reino Unido | <https://www.legislation.gov.uk> · Hansard <https://hansard.parliament.uk> | ONS <https://www.ons.gov.uk> |
| Francia | Légifrance <https://www.legifrance.gouv.fr> | INSEE <https://www.insee.fr> |
| Alemania | <https://www.recht.bund.de> | Destatis <https://www.destatis.de> |
| Italia | Gazzetta Ufficiale <https://www.gazzettaufficiale.it> | ISTAT <https://www.istat.it> |
| Portugal | Diário da República <https://diariodarepublica.pt> | INE <https://www.ine.pt> |

## Ciencia

| Fuente | Uso |
|---|---|
| PubMed <https://pubmed.ncbi.nlm.nih.gov> | Artículos biomédicos revisados por pares |
| Cochrane Library <https://www.cochranelibrary.com> | Revisiones sistemáticas |
| Retraction Watch Database <https://retractiondatabase.org> | Comprobar si un estudio ha sido retractado |

Advertencias con la ciencia: un estudio aislado no es consenso; los preprints no están revisados por pares; los estudios en animales o in vitro no prueban efectos en humanos.

## Trampas habituales con los datos

- **Paro:** paro registrado (SEPE, mensual) frente a tasa de paro (INE, EPA, trimestral). Son medidas distintas.
- **Población extranjera** frente a población **nacida en el extranjero**: el INE publica las dos.
- **Delitos:** conocidos, esclarecidos y detenciones son cifras distintas. Compara siempre los mismos periodos y la misma tasa por cada 1.000 habitantes.
- **Normas:** anteproyecto, proyecto, aprobación en el Congreso y publicación en el BOE (entrada en vigor) son fases distintas.
- **Presupuestos:** lo presupuestado no es lo ejecutado, y una cifra en euros corrientes no es lo mismo en euros constantes.
- **Encuestas:** mira el margen de error, el tamaño de la muestra y la diferencia entre la estimación y la intención directa de voto.
