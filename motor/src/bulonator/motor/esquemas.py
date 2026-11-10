"""Salidas estructuradas de cada papel y el modelo de ``resultado.json``.

Los valores cerrados (calificaciones, confianzas, tipos de fuente, dictámenes…) se validan contra
``reglas.json``, que es su única fuente.
"""
from __future__ import annotations

import re
from typing import Annotated, Any, Literal, Optional

from pydantic import AliasChoices, BaseModel, BeforeValidator, Field, field_validator, model_validator

from ..nucleo.reglas import calificaciones, reglas

_ID_A = re.compile(r"^A\d+$")
_ID_M = re.compile(r"^M\d+$")


def _de_la_lista(valor: Optional[str], lista, que: str) -> Optional[str]:
    if valor is None:
        return None
    if valor not in lista:
        raise ValueError(f"{que} «{valor}» no válido; usa uno de: {', '.join(lista)}")
    return valor


_ALIAS_CALIFICACION = {"OPINIÓN": "NO VERIFICABLE", "OPINION": "NO VERIFICABLE", "BULO": "FALSO",
                       "FALSO / BULO": "FALSO", "FALSO/BULO": "FALSO"}


def _calificacion(v: str) -> str:
    """Acepta la calificación también con su emoji, en minúsculas o con el subtipo: «❌ FALSO (inventado)»."""
    t = re.sub(r"^[^\wÁÉÍÓÚÑÜ]+", "", (v or "").strip()).upper()
    t = t.split("(")[0].strip().rstrip(":").strip()
    return _de_la_lista(_ALIAS_CALIFICACION.get(t, t), list(calificaciones()), "calificación")


# Tolerancia con formatos casi correctos que dan algunos modelos (sin ambigüedad posible):
# una lista escrita como texto suelto o un texto envuelto en {"text": …}.

def _a_texto(v: Any) -> Any:
    if isinstance(v, dict):
        for clave in ("text", "texto", "contenido", "content"):
            if isinstance(v.get(clave), str):
                return v[clave]
        return " ".join(str(x) for x in v.values() if isinstance(x, (str, int, float)))
    if isinstance(v, list) and all(isinstance(x, (str, dict)) for x in v):
        return "\n\n".join(_a_texto(x) for x in v)
    return v


def _a_lista(v: Any) -> Any:
    if v is None:
        return []
    if isinstance(v, str):
        return [v] if v.strip() else []
    if isinstance(v, dict):
        return [_a_texto(v)]
    if isinstance(v, list):
        return [_a_texto(x) if isinstance(x, dict) else x for x in v]
    return v


Lista = Annotated[list[str], BeforeValidator(_a_lista)]
Texto = Annotated[str, BeforeValidator(_a_texto)]


def _confianza(v: str) -> str:
    v = (v or "").strip().upper()
    return _de_la_lista(v, reglas()["confianzas"], "confianza")


# ---------------------------------------------------------------------------
# Evidencias (comunes a captura, verificador, multimedia y origen)
# ---------------------------------------------------------------------------


class Evidencia(BaseModel):
    """Una entrada del registro de evidencias (formato de formato-evidencias.md)."""

    id: str = Field(description="identificador con el prefijo indicado, p. ej. E-A1-01")
    afirmacion: Optional[str] = Field(None, description="ID de la afirmación o del elemento (A1, M1) o «contenido»; "
                                                       "si falta, se deduce del prefijo")
    fuente: str = Field(description="organismo o autor y título del documento")
    url: Optional[str] = Field(None, description="URL abierta con leer (vacía solo para el tipo herramienta)")
    tipo: str = Field(description="tipo de fuente de reglas.json → tipos_fuente")
    fecha_documento: Optional[str] = None
    cita_literal: str = Field(description="fragmento copiado literalmente del texto abierto, entre comillas")
    ubicacion: Optional[str] = Field(None, description="artículo, página, tabla, minuto…")
    que_demuestra: str
    que_no_demuestra: str
    copia_archivada: Optional[str] = None

    @field_validator("tipo")
    @classmethod
    def _tipo(cls, v: str) -> str:
        return _de_la_lista(v.strip().strip("`").lower(), reglas()["tipos_fuente"], "tipo de fuente")


class Busqueda(BaseModel):
    consulta: str
    herramienta: str
    resultado: str


class InformeAgente(BaseModel):
    """Salida de verificador, multimedia y origen: conclusión propuesta y registro de evidencias."""

    elemento: str = Field(description="texto exacto de la afirmación o descripción del elemento analizado")
    calificacion: str = Field(description="calificación propuesta (reglas.json → calificaciones)")
    subtipo: Optional[str] = None
    confianza: str
    razonamiento: str = Field(description="3-6 frases; cada una cita sus E-…")
    veredicto_multimedia: Optional[str] = Field(None, description="solo multimedia: reglas.json → veredictos_multimedia")
    evidencias: list[Evidencia] = Field(default_factory=list)
    busquedas: list[Busqueda] = Field(default_factory=list, description="búsquedas sin herramienta registrada")
    lagunas: Lista = Field(default_factory=list)

    @field_validator("calificacion")
    @classmethod
    def validar_calificacion(cls, v: str) -> str:
        return _calificacion(v)

    @field_validator("confianza")
    @classmethod
    def validar_confianza(cls, v: str) -> str:
        return _confianza(v)

    @field_validator("veredicto_multimedia")
    @classmethod
    def _vm(cls, v):
        return _de_la_lista(v, reglas()["veredictos_multimedia"], "veredicto multimedia")


# ---------------------------------------------------------------------------
# Captura y desglose
# ---------------------------------------------------------------------------


class ElementoFicha(BaseModel):
    archivo: Optional[str] = None
    url: Optional[str] = None
    descripcion: str = Field("sin describir", description="qué se ve o se oye",
                             validation_alias=AliasChoices("descripcion", "texto_alternativo", "texto_visible"))
    que_se_dice_que_muestra: Optional[str] = None


class Ficha(BaseModel):
    """Ficha del contenido capturado (01-captura.md)."""

    resumen: str
    plataforma: str
    autor: str = Field(description="figura pública, medio u organismo, o «un usuario particular» (anonimizado)")
    autor_es_publico: bool
    fecha_publicacion: Optional[str] = None
    texto_literal: str
    multimedia: list[ElementoFicha] = Field(default_factory=list)
    contenido_incrustado: Lista = Field(default_factory=list)
    senales: Lista = Field(default_factory=list, description="señales de alerta observadas")
    evidencias: list[Evidencia] = Field(default_factory=list, description="evidencias E-C-…")
    limitaciones: Lista = Field(default_factory=list)


class Afirmacion(BaseModel):
    id: str = Field(description="A1, A2…")
    texto: str = Field(description="formulación comprobable: quién, qué, cuándo, dónde, cuánto",
                       validation_alias=AliasChoices("texto", "afirmacion", "enunciado"))
    tipo: str = Field(description="norma, dato, cita, suceso, ciencia-salud, otro")
    quien_tendria_el_dato: str = Field(validation_alias=AliasChoices(
        "quien_tendria_el_dato", "quien_tiene_dato", "quien_tiene_el_dato", "quien_tendria_dato", "fuente_del_dato"))
    prioridad: Literal["central", "alta", "media", "baja"] = "media"

    @field_validator("prioridad", mode="before")
    @classmethod
    def _prioridad(cls, v):
        v = str(v or "media").strip().lower()
        return v if v in ("central", "alta", "media", "baja") else "media"
    palabras_clave: Lista = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _id(cls, v):
        if not _ID_A.match(v):
            raise ValueError("el ID de una afirmación es A1, A2…")
        return v


class ElementoMultimedia(BaseModel):
    id: str = Field(description="M1, M2…")
    archivo: Optional[str] = Field(None, description="ruta en media/ si se descargó")
    url: Optional[str] = None
    que_se_dice_que_muestra: str = Field(validation_alias=AliasChoices("que_se_dice_que_muestra", "descripcion",
                                                                       "que_muestra"))
    que_comprobar: str = Field(validation_alias=AliasChoices("que_comprobar", "que_hay_que_comprobar", "comprobar"))

    @field_validator("id")
    @classmethod
    def _id(cls, v):
        if not _ID_M.match(v):
            raise ValueError("el ID de un elemento multimedia es M1, M2…")
        return v


class Encargo(BaseModel):
    papel: Literal["verificador", "multimedia", "origen"] = Field(
        description="verificador o multimedia; el rastreo de origen se hace siempre y no necesita encargo")

    @field_validator("papel", mode="before")
    @classmethod
    def _papel(cls, v):
        """«bulonator-verificador» o «Verificador» → «verificador»."""
        return re.sub(r"^(bulonator[:-])+", "", str(v or "").strip().lower()).replace("bulonator-", "")
    ids: Lista = Field(description="afirmaciones (A…) o elementos (M…) de este encargo")


class Desglose(BaseModel):
    """Desglose del contenido (02-afirmaciones.md)."""

    como_se_entiende: str
    afirmacion_central: Optional[str] = Field(description="ID de la afirmación central (None si todo es opinión)")
    afirmaciones: list[Afirmacion] = Field(default_factory=list)
    multimedia: list[ElementoMultimedia] = Field(default_factory=list)
    no_verificable: Lista = Field(default_factory=list)
    viralidad: str = ""
    peligrosidad: str = ""
    encargos: list[Encargo] = Field(default_factory=list)
    palabras_clave_origen: Lista = Field(default_factory=list, description="en español y en otros idiomas")

    @model_validator(mode="after")
    def _coherente(self):
        ids_a = [a.id for a in self.afirmaciones]
        ids_m = [m.id for m in self.multimedia]
        if len(set(ids_a)) != len(ids_a) or len(set(ids_m)) != len(ids_m):
            raise ValueError("hay IDs repetidos: cada afirmación (A1, A2…) y cada elemento (M1, M2…) lleva el suyo")
        if ids_a and self.afirmacion_central not in ids_a:
            # Tolerancia sin ambigüedad: el modelo ha escrito el texto en vez del ID, o solo hay una candidata
            self.afirmacion_central = self._central_deducida()
            if self.afirmacion_central is None:
                raise ValueError("«afirmacion_central» tiene que ser el ID de una de las afirmaciones de la lista "
                                 f"({', '.join(ids_a)}), por ejemplo «{ids_a[0]}», no su texto")
        validos = set(ids_a) | set(ids_m)
        # Los encargos vacíos no aportan nada, y el rastreo de origen se lanza siempre, con o sin encargo
        self.encargos = [e for e in self.encargos if e.ids and e.papel != "origen"]
        for e in self.encargos:
            fuera = set(e.ids) - validos
            if fuera:
                raise ValueError(f"encargo con IDs que no están en las listas: {', '.join(sorted(fuera))} "
                                 f"(válidos: {', '.join(sorted(validos))})")
        return self

    def _central_deducida(self) -> Optional[str]:
        def plano(s: str) -> str:
            return re.sub(r"\W+", " ", (s or "").casefold()).strip()

        escrito = plano(self.afirmacion_central or "")
        if escrito:
            por_texto = [a.id for a in self.afirmaciones if plano(a.texto) == escrito
                         or (len(escrito) > 20 and (escrito in plano(a.texto) or plano(a.texto) in escrito))]
            if len(por_texto) == 1:
                return por_texto[0]
        centrales = [a.id for a in self.afirmaciones if a.prioridad == "central"]
        if len(centrales) == 1:
            return centrales[0]
        if len(self.afirmaciones) == 1:
            return self.afirmaciones[0].id
        if escrito:  # por parecido, solo si una afirmación destaca claramente sobre las demás
            palabras = set(escrito.split())
            parecidos = sorted(((len(palabras & set(plano(a.texto).split())) / max(1, len(palabras | set(plano(a.texto).split()))), a.id)
                                for a in self.afirmaciones), reverse=True)
            if parecidos and parecidos[0][0] >= 0.25 and (len(parecidos) == 1 or parecidos[0][0] >= 1.5 * parecidos[1][0]):
                return parecidos[0][1]
        return None


# ---------------------------------------------------------------------------
# Redacción y auditoría
# ---------------------------------------------------------------------------


class Apartado(BaseModel):
    id: str = Field(description="A1… o M1…")
    titulo: str = Field(description="la afirmación o el elemento")
    valoracion: str = Field(description="calificación parcial, p. ej. «FALSO (inventado)» o «descontextualizado»",
                            validation_alias=AliasChoices("valoracion", "calificacion", "calificacion_parcial"))
    explicacion: str = Field(description="explicación con datos y citas breves, cada una con su [n]",
                             validation_alias=AliasChoices("explicacion", "razonamiento", "texto"))

    @field_validator("valoracion")
    @classmethod
    def _valoracion(cls, v: str) -> str:
        """«alerta (sin pruebas)» → «ALERTA (sin pruebas)»: la calificación va en mayúsculas, como en la escala."""
        limpio = re.sub(r"^[^\wÁÉÍÓÚÑÜ]+", "", (v or "").strip())
        for nombre in sorted(calificaciones(), key=len, reverse=True):
            if limpio.upper().startswith(nombre):
                return nombre + limpio[len(nombre):]
        return v
    evidencias: Lista = Field(default_factory=list, description="IDs E-… en los que se apoya")


class Fuente(BaseModel):
    n: int
    autor: str = Field(description="organismo o autor")
    titulo: str
    fecha: Optional[str] = None
    url: str = Field(description="URL de una evidencia (o su copia archivada si es el contenido original)")
    copia: Optional[str] = None
    tipo: str
    evidencias: Lista = Field(default_factory=list)

    @field_validator("tipo")
    @classmethod
    def _tipo(cls, v: str) -> str:
        return _de_la_lista(v.strip().strip("`").lower(), reglas()["tipos_fuente"], "tipo de fuente")


class Publicaciones(BaseModel):
    breve: Texto
    hilo_x: Lista = Field(default_factory=list)
    largo: Optional[Texto] = None
    mensajeria: Texto
    texto_alternativo: Optional[Texto] = None

    @field_validator("breve", "mensajeria")
    @classmethod
    def _con_texto(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("esta publicación es obligatoria y no puede ir vacía")
        return v


class Redaccion(BaseModel):
    """Informe y textos para redes (informe.md y publicacion.md)."""

    calificacion: str
    subtipo: Optional[str] = None
    confianza: str
    titular: str = Field(description="titular en forma de sándwich de la verdad, sin la etiqueta")
    resumen: str = Field(description="3-5 frases; cada dato con [n]")
    que_circula: Lista = Field(default_factory=list, description="viñetas: formato, quién, alcance… con [n]")
    afirmacion_central_cita: str = Field("", description="cita breve de la afirmación central")
    apartados: list[Apartado] = Field(default_factory=list, description="un apartado por afirmación y por elemento")
    origen_y_difusion: str = ""
    por_que: str = Field(description="por qué esta categoría y no la vecina")
    limitaciones: Lista = Field(default_factory=list)
    replica: str = ""
    fuentes: list[Fuente] = Field(default_factory=list)
    herramientas: Lista = Field(default_factory=list)
    publicaciones: Publicaciones

    @field_validator("calificacion")
    @classmethod
    def validar_calificacion(cls, v: str) -> str:
        return _calificacion(v)

    @field_validator("confianza")
    @classmethod
    def validar_confianza(cls, v: str) -> str:
        return _confianza(v)

    @model_validator(mode="after")
    def _reglas(self):
        conf = calificaciones()[self.calificacion]
        if self.confianza not in conf["confianzas"]:
            raise ValueError(f"la confianza {self.confianza} no está permitida con {self.calificacion}")
        if self.subtipo and self.subtipo not in conf["subtipos"]:
            raise ValueError(f"subtipo «{self.subtipo}» no válido para {self.calificacion}")
        numeros = [f.n for f in self.fuentes]
        if numeros != list(range(1, len(numeros) + 1)):
            raise ValueError("numera las fuentes 1, 2, 3… sin huecos y en orden")
        return self


class Cambio(BaseModel):
    ubicacion: str
    problema: str
    correccion: str


class FilaTrazabilidad(BaseModel):
    frase: str
    referencia: str
    estado: Literal["OK", "SIN EVIDENCIA", "EXCEDE LA EVIDENCIA", "INCOHERENTE"]


class Dictamen(BaseModel):
    """Dictamen del auditor (03-auditoria.md)."""

    dictamen: str = Field(description="PALANTE, CAMBIOS o VETO")
    resumen: str
    cambios_obligatorios: list[Cambio] = Field(default_factory=list)
    recomendados: Lista = Field(default_factory=list)
    afecta_a_calificacion_o_cifras: bool = Field(False, description="¿algún cambio afecta a la calificación o a una cifra?")
    motivo_veto: Optional[str] = None
    trazabilidad: list[FilaTrazabilidad] = Field(default_factory=list)
    fuentes_reabiertas: Lista = Field(default_factory=list, description="«fuente: resultado» de cada fuente reabierta")

    @field_validator("dictamen")
    @classmethod
    def _dictamen(cls, v: str) -> str:
        return _de_la_lista(v.strip().upper(), reglas()["auditoria"]["dictamenes"], "dictamen")

    @model_validator(mode="after")
    def _coherente(self):
        if self.dictamen == "CAMBIOS" and not self.cambios_obligatorios:
            raise ValueError("un dictamen CAMBIOS necesita al menos un cambio obligatorio")
        if self.dictamen == "VETO" and not self.motivo_veto:
            raise ValueError("un VETO necesita su motivo y qué haría falta para levantarlo")
        return self


# ---------------------------------------------------------------------------
# resultado.json
# ---------------------------------------------------------------------------


class EntradaResultado(BaseModel):
    valor: Optional[str] = None
    tipo: Optional[str] = None
    plataforma: Optional[str] = None
    copia_archivada: Optional[str] = None


class AfirmacionResultado(BaseModel):
    id: str
    texto: str
    calificacion: Optional[str] = None
    valoracion: str = ""
    evidencias: list[str] = Field(default_factory=list)


class MultimediaResultado(BaseModel):
    id: str
    descripcion: str
    veredicto: str = ""
    evidencias: list[str] = Field(default_factory=list)


class FuenteResultado(BaseModel):
    n: int
    referencia: str
    url: Optional[str] = None
    copia: Optional[str] = None
    tipo: Optional[str] = None
    evidencias: list[str] = Field(default_factory=list)


class AuditoriaResultado(BaseModel):
    rondas: int
    dictamen: str
    aprobado: bool
    cierre: bool = False


class Resultado(BaseModel):
    """Contenido de ``resultado.json`` (el mismo que genera el plugin de Claude Code)."""

    version: int
    bulonator: str
    caso: str
    fecha: str
    generado_por: str
    idioma: str
    entrada: EntradaResultado
    calificacion: str
    subtipo: Optional[str] = None
    confianza: str
    titular: str
    resumen: str
    afirmacion_central: Optional[str] = None
    afirmaciones: list[AfirmacionResultado] = Field(default_factory=list)
    multimedia: list[MultimediaResultado] = Field(default_factory=list)
    fuentes: list[FuenteResultado] = Field(default_factory=list)
    publicaciones: dict = Field(default_factory=dict)
    limitaciones: list[str] = Field(default_factory=list)
    replica: Optional[str] = None
    auditoria: AuditoriaResultado
    modelos: dict = Field(default_factory=dict)
    archivos: dict = Field(default_factory=dict)

    @property
    def etiqueta(self) -> str:
        return calificaciones()[self.calificacion]["etiqueta"]

    @property
    def textos(self) -> dict:
        """Alias de ``publicaciones``."""
        return self.publicaciones
