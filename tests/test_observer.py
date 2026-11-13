"""Pruebas del patrón Observer: PublicadorEventos y Suscriptor."""

import unittest

from banco_senior import traza
from banco_senior.eventos import AbonoRegistrado, CuentaBloqueada
from banco_senior.observer import PublicadorEventos, Suscriptor


def setUpModule():
    traza.ACTIVA = False


def tearDownModule():
    traza.ACTIVA = True


class SuscriptorEspia(Suscriptor):
    """Doble de prueba: guarda los eventos que recibe."""

    def __init__(self):
        self.recibidos = []

    def actualizar(self, evento):
        self.recibidos.append(evento)


class SuscriptorQueFalla(Suscriptor):
    def actualizar(self, evento):
        raise ConnectionError("operador caído")


def un_abono(documento="1001001"):
    return AbonoRegistrado(
        documento, "Rosa Elena Martínez", 1423500, "2026-11", "TX-0001"
    )


class PruebasObserver(unittest.TestCase):

    def test_publicar_entrega_el_evento_a_todos_los_suscriptores(self):
        publicador = PublicadorEventos()
        a, b = SuscriptorEspia(), SuscriptorEspia()
        publicador.suscribir(a)
        publicador.suscribir(b)
        evento = un_abono()
        publicador.publicar(evento)
        self.assertEqual(a.recibidos, [evento])
        self.assertEqual(b.recibidos, [evento])

    def test_un_suscriptor_nuevo_no_requiere_cambiar_al_publicador(self):
        # El publicador funciona con cualquier clase que implemente Suscriptor,
        # incluso una que no existía cuando se escribió (aquí, un espía de prueba).
        publicador = PublicadorEventos()
        nuevo = SuscriptorEspia()
        publicador.suscribir(nuevo)
        publicador.publicar(CuentaBloqueada("1001004", minutos=30))
        self.assertEqual([e.tipo for e in nuevo.recibidos], ["CuentaBloqueada"])

    def test_el_suscriptor_solo_recibe_eventos_posteriores_a_su_suscripcion(self):
        publicador = PublicadorEventos()
        tardio = SuscriptorEspia()
        publicador.publicar(un_abono("1001001"))
        publicador.suscribir(tardio)
        publicador.publicar(un_abono("1001003"))
        self.assertEqual([e.documento for e in tardio.recibidos], ["1001003"])

    def test_desuscribir_deja_de_entregar_eventos(self):
        publicador = PublicadorEventos()
        espia = SuscriptorEspia()
        publicador.suscribir(espia)
        publicador.desuscribir(espia)
        publicador.publicar(un_abono())
        self.assertEqual(espia.recibidos, [])

    def test_suscribir_dos_veces_no_duplica_la_entrega(self):
        publicador = PublicadorEventos()
        espia = SuscriptorEspia()
        publicador.suscribir(espia)
        publicador.suscribir(espia)
        publicador.publicar(un_abono())
        self.assertEqual(len(espia.recibidos), 1)

    def test_un_suscriptor_que_falla_no_impide_que_los_demas_reciban(self):
        publicador = PublicadorEventos()
        espia = SuscriptorEspia()
        publicador.suscribir(SuscriptorQueFalla())
        publicador.suscribir(espia)
        publicador.publicar(un_abono())
        self.assertEqual(len(espia.recibidos), 1)

    def test_suscriptor_es_una_interfaz_que_obliga_a_implementar_actualizar(self):
        class SinActualizar(Suscriptor):
            pass

        with self.assertRaises(TypeError):
            SinActualizar()


if __name__ == "__main__":
    unittest.main()
