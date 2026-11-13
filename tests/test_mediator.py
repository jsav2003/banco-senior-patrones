"""Pruebas del patrón Mediator: MediadorModulos, Modulo y las solicitudes."""

import unittest

from banco_senior import traza
from banco_senior.auditoria import Auditoria
from banco_senior.gestion_usuario import Contacto, GestionUsuario
from banco_senior.mediator import (
    ConsultarContacto,
    EnviarCodigo,
    Mediador,
    MediadorModulos,
    RegistrarResultado,
    Solicitud,
)
from banco_senior.notificaciones import Notificaciones
from banco_senior.observer import PublicadorEventos
from banco_senior.simuladores import OperadorMensajeriaSimulado


def setUpModule():
    traza.ACTIVA = False


def tearDownModule():
    traza.ACTIVA = True


class MediadorDePrueba(Mediador):
    """Doble de prueba: responde ConsultarContacto y guarda lo que le piden.

    Permite probar Notificaciones sin crear GestionUsuario ni Auditoria.
    """

    def __init__(self):
        self.pedidos = []

    def notificar(self, emisor, solicitud):
        self.pedidos.append(solicitud)
        if isinstance(solicitud, ConsultarContacto):
            return Contacto(
                "Rosa Elena Martínez", "3001110001", "rosa.martinez@correo.test"
            )
        return None


def modulos_conectados():
    operador = OperadorMensajeriaSimulado()
    gestion = GestionUsuario(PublicadorEventos())
    notificaciones = Notificaciones(operador)
    auditoria = Auditoria()
    mediador = MediadorModulos(gestion, notificaciones, auditoria)
    return mediador, gestion, notificaciones, auditoria, operador


class PruebasMediator(unittest.TestCase):

    def test_notificaciones_se_prueba_sola_con_un_mediador_de_prueba(self):
        operador = OperadorMensajeriaSimulado()
        notificaciones = Notificaciones(operador)
        mediador = MediadorDePrueba()
        notificaciones.conectar(mediador)
        notificaciones.preferir_canal("1001001", "correo")

        entregado = notificaciones.enviar_aviso("1001001", "correo", "prueba")

        self.assertTrue(entregado)
        self.assertEqual(
            operador.enviados[0][1:3], ("correo", "rosa.martinez@correo.test")
        )
        self.assertEqual(
            [type(p).__name__ for p in mediador.pedidos],
            ["ConsultarContacto", "RegistrarResultado"],
        )

    def test_el_mediador_lleva_consultar_contacto_a_gestion_de_usuario(self):
        mediador, gestion, notificaciones, _, _ = modulos_conectados()
        gestion.cargar_pensionado(
            "1001003", "Carmen Lucía Ríos", "3001110003", "carmen.rios@correo.test"
        )
        contacto = mediador.notificar(notificaciones, ConsultarContacto("1001003"))
        self.assertEqual(contacto.correo, "carmen.rios@correo.test")

    def test_el_registro_pide_el_codigo_y_sale_por_el_canal_preferido(self):
        # Ida y vuelta por el mediador: GestionUsuario -> Notificaciones -> GestionUsuario.
        mediador, gestion, notificaciones, auditoria, operador = modulos_conectados()
        notificaciones.preferir_canal("1001005", "correo")
        enviado = gestion.registrar(
            "1001005", "Ana Beatriz Gómez", "3001110005", "ana.gomez@correo.test"
        )
        self.assertTrue(enviado)
        _, canal, destino, mensaje = operador.enviados[0]
        self.assertEqual((canal, destino), ("correo", "ana.gomez@correo.test"))
        self.assertIn("código de verificación", mensaje)
        self.assertEqual(mediador.solicitudes_atendidas["EnviarCodigo"], 1)
        self.assertEqual(auditoria.registros[-1].tipo, "Aviso enviado")

    def test_registrar_resultado_llega_a_auditoria(self):
        mediador, _, notificaciones, auditoria, _ = modulos_conectados()
        mediador.notificar(
            notificaciones, RegistrarResultado("aviso", "1001002", False, "sms")
        )
        self.assertEqual(auditoria.registros[0].tipo, "Aviso FALLIDO")

    def test_el_mediador_rechaza_una_solicitud_que_no_conoce(self):
        class Desconocida(Solicitud):
            pass

        mediador, gestion, _, _, _ = modulos_conectados()
        with self.assertRaises(ValueError):
            mediador.notificar(gestion, Desconocida())

    def test_un_modulo_sin_mediador_avisa_con_un_error_claro(self):
        notificaciones = Notificaciones(OperadorMensajeriaSimulado())
        with self.assertRaisesRegex(RuntimeError, "no está conectado"):
            notificaciones.enviar_codigo("1001001", "123456")

    def test_los_modulos_solo_guardan_referencia_al_mediador(self):
        mediador, gestion, notificaciones, auditoria, _ = modulos_conectados()
        modulos = (gestion, notificaciones, auditoria)
        for modulo in modulos:
            self.assertIs(modulo._mediador, mediador)
            for valor in vars(modulo).values():
                self.assertFalse(
                    any(valor is otro for otro in modulos if otro is not modulo),
                    f"{type(modulo).__name__} guarda una referencia a otro módulo",
                )


if __name__ == "__main__":
    unittest.main()
