class OddsHelper:

    def group_phase_result(self, score_a, score_b, pred_a, pred_b):
        """"
        Calcula a pontuação para um palpite na fase de grupos, considerando o resultado exato e o saldo de gols.
         - 10 pontos para o resultado exato (placar correto)
         - 5 pontos para o saldo de gols correto (diferença entre os placares)
         - 0 pontos para qualquer outro resultado

         Params:
            - score_a: Placar real do time A
            - score_b: Placar real do time B
            - pred_a: Placar previsto do time A
            - pred_b: Placar previsto do time B
        """
        if score_a is None or score_b is None:
            return 0

        real_diff = score_a - score_b # Saldo de gols real
        pred_diff = pred_a - pred_b # Saldo de gols do palpite

        def sign(x):
            if x > 0: return 1
            if x == 0: return 0
            return -1

        if score_a == pred_a and score_b == pred_b:
            return 10
        elif real_diff == pred_diff:
            return 5
        elif sign(real_diff) == sign(pred_diff):
            return 2
        return 0

    def knockout_phase_result(self, score_a, score_b, pred_a, pred_b, winner_real, winner_pred, pen_a=None, pen_b=None, p_pen_a=None, p_pen_b=None):
        if score_a is None or score_b is None:
            return 0

        saldo_real = score_a - score_b
        saldo_palpite = pred_a - pred_b

        fdd_real = 1 if saldo_real == 0 else 0
        fdd_palpite = 1 if saldo_palpite == 0 else 0

        # Determina Classificado Real (C) e Palpitado (Cx)
        # Se não for empate, o vencedor é óbvio pelo placar. Se for empate, usa o campo winner.
        if score_a != score_b:
            c_real = 'A' if score_a > score_b else 'B'
        else:
            c_real = 'A' if (pen_a or 0) > (pen_b or 0) else 'B' if (pen_b or 0) > (pen_a or 0) else winner_real

        if pred_a != pred_b:
            c_pred = 'A' if pred_a > pred_b else 'B'
        else:
            c_pred = 'A' if (p_pen_a or 0) > (p_pen_b or 0) else 'B' if (p_pen_b or 0) > (p_pen_a or 0) else winner_pred

        cx_eq_c = (c_real is not None and c_real == c_pred)

        # Regras hierárquicas
        if cx_eq_c and pred_a == score_a and pred_b == score_b:
            return 15
        elif cx_eq_c and saldo_palpite == saldo_real:
            return 8
        elif cx_eq_c and fdd_palpite == fdd_real:
            return 6
        elif cx_eq_c:
            return 5
        elif pred_a == score_a and pred_b == score_b:
            return 2
        elif saldo_palpite == saldo_real:
            return 1
        elif fdd_palpite == fdd_real:
            return 1
        return 0
