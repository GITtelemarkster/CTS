from typing import Dict, Any
from models import ClockNode, WireModel
from delay_calc import DelayCalculator

class CTSOptimizer:
    """
    Модуль постоптимизации дерева синхронизации.
    Выравнивает задержки ветвей с помощью механизма Wire Snaking (добавление змеевиков).
    """
    def __init__(self, wire_model: WireModel, opt_params: Dict[str, Any]):
        self.wire_model = wire_model
        self.params = opt_params
        
        # Извлечение параметров оптимизации
        self.objective = opt_params.get("objective", "min_skew")
        self.max_iterations = int(opt_params.get("max_iterations", 20))
        self.convergence_tol = float(opt_params.get("convergence_tol", 1e-4))
        self.skew_target = float(opt_params.get("skew_target", 0.05))
        self.snaking_allowed = opt_params.get("snaking_allowed", True)
        self.wire_snaking_limit = float(opt_params.get("wire_snaking_limit", 0.2))

        # Инициализируем внутренний калькулятор для оценки изменений на каждой итерации
        self.delay_calculator = DelayCalculator(wire_model)

    def optimize(self, root: ClockNode) -> Tuple[Dict[str, float], float]:
        """
        Основной цикл оптимизации. Итеративно подгоняет задержки быстрых веток.
        Возвращает итоговые задержки и финальный skew.
        """
        # Первичный расчет задержек до оптимизации
        sink_delays, current_skew = self.delay_calculator.calculate(root)
        
        if not sink_delays or current_skew <= self.skew_target or not self.snaking_allowed:
            return sink_delays, current_skew

        previous_skew = current_skew

        # Итеративный процесс оптимизации
        for iteration in range(self.max_iterations):
            max_delay = max(sink_delays.values())
            
            # Обходим дерево и добавляем дополнительную длину проводов на быстрых путях
            self._apply_snaking_recursive(root, max_delay)
            
            # Пересчитываем задержки после изменения длин
            sink_delays, current_skew = self.delay_calculator.calculate(root)
            
            # Проверка условий досрочного выхода
            if current_skew <= self.skew_target:
                break
                
            if abs(previous_skew - current_skew) < self.convergence_tol:
                break
                
            previous_skew = current_skew

        return sink_delays, current_skew

    def _apply_snaking_recursive(self, node: ClockNode, target_max_delay: float):
        """
        Рекурсивный обход дерева для локального удлинения сегментов (Snaking).
        """
        for child in node.children:
            # Если дочерний узел (или его поддерево) существенно быстрее целевой максимальной задержки
            if child.delay_from_source < target_max_delay:
                # Вычисляем дефицит задержки, который нужно компенсировать
                delay_deficit = target_max_delay - child.delay_from_source
                
                # Рассчитаем, сколько физической длины провода нужно добавить для компенсации.
                # Из модели Элмора: d_delay ≈ R_wire * C_load + R_driver * C_wire
                # Упрощенно аппроксимируем необходимую добавку длины через параметры модели проводов:
                r_unit = self.wire_model.unit_resistance
                c_unit = self.wire_model.unit_capacitance
                c_load = child.downstream_capacitance
                
                # Нам нужно решить уравнение: delay_deficit = L_add * r_unit * c_load
                # Берем базовый вклад сопротивления провода на емкость нагрузки
                denominator = (r_unit * c_load) if c_load > 0 else 1.0
                additional_length = delay_deficit / denominator
                
                # Защита: ограничиваем максимальное удлинение лимитом из ТЗ (wire_snaking_limit),
                # чтобы длина провода не росла бесконечно
                max_allowed_extension = child.wire_length_to_parent * self.wire_snaking_limit
                if additional_length > max_allowed_extension:
                    additional_length = max_allowed_extension
                
                # Увеличиваем физическую длину провода (эффект "змеевика")
                child.wire_length_to_parent += additional_length

            # Спускаемся глубже по дереву
            self._apply_snaking_recursive(child, target_max_delay)
