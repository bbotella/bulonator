"""Salidas estructuradas de cada papel y el modelo de ``resultado.json``.

Los valores cerrados (calificaciones, confianzas, tipos de fuente, dictámenes…) se validan contra
``reglas.json``, que es su única fuente.
"""
from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from ..nucleo.reglas import calificaciones, reglas

_ID_A = re.compile(r"^A\d+$")
_ID_M = re.compile(r"^M\d+$")


def _de_la_lista(valor: Optional[str], lista, que: str) -> Optional[str]:
    if valor is None:
        return None
    if valor not in lista:
        raise ValueError(f"{que} «{valor}» no válido; usa uno de: {', '.join(lista)}")
    return valor


def _calificacion(v: str) -> str:
    v = (v or "").strip().upper()
    return _de_la_lista(v, list(calificaciones()), "calificación")


def _confianza(v: str) -> str:
    v = (v or "").strip().upper()
    return _de_la_lista(v, reglas()["confianzas"], "confianza")


# ---------------------------------------------------------------------------
# Evidencias (comunes a captura, verificador, multimedia y origen)
# ---------------------------------------------------------------------------


class Evidencia(BaseModel):
    """Una entrada del registro de evidencias (formato de formato-evidencias.md)."""

    id: str = Field(description="identificador con el prefijo indicado, p. ej. E-A1-01")
    afirmacion: str = Field(description="ID de la afirmación o del elemento (A1, M1) o «contenido»")
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
    lagunas: list[str] = Field(default_factory=list)

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
    descripcion: str = Field(description="qué se ve o se oye")
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
    contenido_incrustado: list[str] = Field(default_factory=list)
    senales: list[str] = Field(default_factory=list, description="señales de alerta observadas")
    evidencias: list[Evidencia] = Field(default_factory=list, description="evidencias E-C-…")
    limitaciones: list[str] = Field(default_factory=list)


class Afirmacion(BaseModel):
    id: str = Field(description="A1, A2…")
    texto: str = Field(description="formulación comprobable: quién, qué, cuándo, dónde, cuánto")
    tipo: str = Field(description="norma, dato, cita, suceso, ciencia-salud, otro")
    quien_tendria_el_dato: str
    prioridad: Literal["central", "alta", "media", "baja"] = "media"
    palabras_clave: list[str] = Field(default_factory=list)

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
    que_se_dice_que_muestra: str
    que_comprobar: str

    @field_validator("id")
    @classmethod
    def _id(cls, v):
        if not _ID_M.match(v):
            raise ValueError("el ID de un elemento multimedia es M1, M2…")
        return v


class Encargo(BaseModel):
    papel: Literal["verificador", "multimedia"]
    ids: list[str] = Field(description="afirmaciones (A…) o elementos (M…) de este encargo")


class Desglose(BaseModel):
    """Desglose del contenido (02-afirmaciones.md)."""

    como_se_entiende: str
    afirmacion_central: Optional[str] = Field(description="ID de la afirmación central (None si todo es opinión)")
    afirmaciones: list[Afirmacion] = Field(default_factory=list)
    multimedia: list[ElementoMultimedia] = Field(default_factory=list)
    no_verificable: list[str] = Field(default_factory=list)
    viralidad: str = ""
    peligrosidad: str = ""
    encargos: list[Encargo] = Field(default_factory=list)
    palabras_clave_origen: list[str] = Field(default_factory=list, description="en español y en otros idiomas")

    @model_validator(mode="after")
    def _coherente(self):
        ids_a = [a.id for a in self.afirmaciones]
        ids_m = [m.id for m in self.multimedia]
        if len(set(ids_a)) != len(ids_a) or len(set(ids_m)) != len(ids_m):
            raise ValueError("hay IDs repetidos")
        if self.afirmacion_central and self.afirmacion_central not in ids_a:
            raise ValueError(f"la afirmación central {self.afirmacion_central} no está en la lista")
        if ids_a and not self.afirmacion_central:
            raise ValueError("indica la afirmación central")
        validos = set(ids_a) | set(ids_m)
        for e in self.encargos:
            fuera = set(e.ids) - validos
            if fuera:
                raise ValueError(f"encargo con IDs inexistentes: {', '.join(sorted(fuera))}")
        return self


# ---------------------------------------------------------------------------
# Redacción y auditoría
# ---------------------------------------------------------------------------


class Apartado(BaseModel):
    id: str = Field(description="A1… o M1…")
    titulo: str = Field(description="la afirmación o el elemento")
    valoracion: str = Field(description="calificación parcial, p. ej. «FALSO (inventado)» o «descontextualizado»")
    explicacion: str = Field(description="explicación con datos y citas breves, cada una con su [n]")
    evidencias: list[str] = Field(default_factory=list, description="IDs E-… en los que se apoya")


class Fuente(BaseModel):
    n: int
    autor: str = Field(description="organismo o autor")
    titulo: str
    fecha: Optional[str] = None
    url: str = Field(description="URL de una evidencia (o su copia archivada si es el contenido original)")
    copia: Optional[str] = None
    tipo: str
    evidencias: list[str] = Field(default_factory=list)

    @field_validator("tipo")
    @classmethod
    def _tipo(cls, v: str) -> str:
        return _de_la_lista(v.strip().strip("`").lower(), reglas()["tipos_fuente"], "tipo de fuente")


class Publicaciones(BaseModel):
    breve: str
    hilo_x: list[str] = Field(default_factory=list)
    largo: Optional[str] = None
    mensajeria: str
    texto_alternativo: Optional[str] = None


class Redaccion(BaseModel):
    """Informe y textos para redes (informe.md y publicacion.md)."""

    calificacion: str
    subtipo: Optional[str] = None
    confianza: str
    titular: str = Field(description="titular en forma de sándwich de la verdad, sin la etiqueta")
    resumen: str = Field(description="3-5 frases; cada dato con [n]")
    que_circula: list[str] = Field(default_factory=list, description="viñetas: formato, quién, alcance… con [n]")
    afirmacion_central_cita: str = Field("", description="cita breve de la afirmación central")
    apartados: list[Apartado] = Field(default_factory=list, description="un apartado por afirmación y por elemento")
    origen_y_difusion: str = ""
    por_que: str = Field(description="por qué esta categoría y no la vecina")
    limitaciones: list[str] = Field(default_factory=list)
    replica: str = ""
    fuentes: list[Fuente] = Field(default_factory=list)
    herramientas: list[str] = Field(default_factory=list)
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
    recomendados: list[str] = Field(default_factory=list)
    afecta_a_calificacion_o_cifras: bool = Field(False, description="¿algún cambio afecta a la calificación o a una cifra?")
    motivo_veto: Optional[str] = None
    trazabilidad: list[FilaTrazabilidad] = Field(default_factory=list)
    fuentes_reabiertas: list[str] = Field(default_factory=list, description="«fuente: resultado» de cada fuente reabierta")

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
