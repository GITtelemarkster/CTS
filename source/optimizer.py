import math
from typing import Dict, Any, Tuple
from models import ClockNode, WireModel
from delay_calc import DelayCalculator

class CTSOptimizer:
    """
    Модуль постоптимизации дерева синхронизации.
    Выравнивает задержки ветвей с помощью точного механизма Wire Snaking (модель Элмора).
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
        Учитывает собственную емкость провода и выходное сопротивление родительского драйвера.
        """
        # Извлекаем сопротивление драйвера текущего узла (родителя для дочерних сегментов)
        # Предполагается, что у BufferType есть поле output_resistance (или drive_resistance)
        r_driver = 0.0
        if hasattr(node, 'buffer_ref') and node.buffer_ref:
            # Пытаемся получить выходное сопротивление буфера
            r_driver = getattr(node.buffer_ref, 'output_resistance', 0.0)
        elif node.node_type == "source":
            # Для корня дерева можно взять внутреннее сопротивление источника тактовой частоты
            r_driver = getattr(node, 'source_resistance', 0.0)

        for child in node.children:
            # Если дочерний узел (или его поддерево) существенно быстрее целевой максимальной задержки
            if child.delay_from_source < target_max_delay:
                # Вычисляем дефицит задержки, который нужно компенсировать
                delay_deficit = target_max_delay - child.delay_from_source
                
                # Параметры модели проводов
                r_unit = self.wire_model.unit_resistance
                c_unit = self.wire_model.unit_capacitance
                c_load = child.downstream_capacitance
                
                # ИЗМЕНЕНО: Решаем полное квадратное уравнение задержки Элмора:
                # a * L_add^2 + b * L_add + c = 0
                a = 0.5 * r_unit * c_unit
                b = (r_unit * c_load) + (r_driver * c_unit)
                c = -delay_deficit
                
                # Дискриминант (всегда положителен, так как a > 0 и c < 0)
                discriminant = b**2 - 4 * a * c
                
                if a > 0:
                    # Берем единственный положительный корень квадратного уравнения
                    additional_length = (-b + math.sqrt(discriminant)) / (2 * a)
                else:
                    # На случай, если параметры провода нулевые (защита от деления на 0)
                    additional_length = delay_deficit / b if b > 0 else 0.0
                
                # Защита: ограничиваем максимальное удлинение лимитом из конфигурации
                max_allowed_extension = child.wire_length_to_parent * self.wire_snaking_limit
                if additional_length > max_allowed_extension:
                    additional_length = max_allowed_extension
                
                # Увеличиваем физическую длину провода (эффект "змеевика")
                child.wire_length_to_parent += additional_length

            # Спускаемся глубже по дереву
            self._apply_snaking_recursive(child, target_max_delay)
