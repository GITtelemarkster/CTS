import os
import sys
import time
from parser import CTSParser
from median_partition import MedianPartitionCTS
from delay_calc import DelayCalculator
from optimizer import CTSOptimizer
from validator import CTSValidator
from visualizer import CTSVisualizer

def print_divider():
    print("-" * 60)

def main():
    # Задаем пути к файлам
    input_file = os.path.join("data", "input.json")
    output_file = os.path.join("data", "output.txt")
    image_file = os.path.join("data", "clock_tree.png")
    
    # Создаем директорию для данных, если её нет
    os.makedirs("data", exist_ok=True)
    
    if not os.path.exists(input_file):
        print(f"[Ошибка] Пожалуйста, положите входной JSON-файл по пути: {input_file}")
        sys.exit(1)
        
    print_divider()
    print("=== ЗАПУСК СИНТЕЗА ЦЕПЕЙ СИНХРОНИЗАЦИИ (CTS) ===")
    print_divider()
    
    start_time = time.time()
    
    # 1. Шаг Парсинга
    print("[1/6] Чтение и валидация конфигурации JSON...")
    parser = CTSParser(input_file)
    try:
        clock_source, sinks, buffers, wire_model, tree_params, opt_params = parser.parse()
        print(f"-> Успешно загружено потребителей (Sinks): {len(sinks)}")
        print(f"-> Доступно типов буферов: {len(buffers)}")
        print(f"-> Выбранная модель проводов: {wire_model.model.upper()}")
    except Exception as e:
        print(f"[Критическая ошибка парсинга]: {e}")
        sys.exit(1)
        
    # 2. Шаг Синтеза дерева (Алгоритм медианного разбиения)
    print("[2/6] Запуск рекурсивного медианного разбиения...")
    cts_engine = MedianPartitionCTS(clock_source, sinks, buffers, tree_params)
    root_node = cts_engine.build_tree()
    print("-> Топология дерева успешно построена.")
    
    # 3. Первичный расчет задержек
    print("[3/6] Расчет первоначальных задержек...")
    calculator = DelayCalculator(wire_model)
    initial_delays, initial_skew = calculator.calculate(root_node)
    print(f"-> Исходный разброс задержек (Initial Skew): {initial_skew:.4f} нс")
    
    # 4. Постоптимизация (Выравнивание веток / Snaking)
    print("[4/6] Оптимизация дерева (Wire Snaking)...")
    optimizer = CTSOptimizer(wire_model, opt_params)
    final_delays, final_skew = optimizer.optimize(root_node)
    print(f"-> Финальный разброс задержек (Final Skew): {final_skew:.4f} нс")
    
    # 5. Верификация результатов (Валидатор)
    print("[5/6] Верификация физических и временных ограничений...")
    validator = CTSValidator(
        max_fanout=int(tree_params.get("max_fanout", 4)),
        max_depth=int(tree_params.get("max_depth", 10)),
        chip_width=parser.chip_width,
        chip_height=parser.chip_height,
        available_buffers=buffers
    )
    is_valid, errors, warnings = validator.validate(root_node, len(sinks), final_delays)
    
    execution_time = time.time() - start_time
    
    # Вывод результатов проверки в консоль
    if is_valid:
        print("-> [УСПЕХ] Дерево синхронизации успешно прошло все проверки!")
    else:
        print(f"-> [ОШИБКА] Обнаружено ошибок при верификации: {len(errors)}")
        for err in errors:
            print(f"   ! {err}")
            
    if warnings:
        print(f"-> [ПРЕДУПРЕЖДЕНИЕ] Найдено замечаний: {len(warnings)}")
        for warn in warnings:
            print(f"   * {warn}")
            
    # 6. Отрисовка полученной топологии
    print("[6/6] Генерация графического отчета...")
    try:
        visualizer = CTSVisualizer(parser.chip_width, parser.chip_height)
        visualizer.plot_tree(root_node, save_path=image_file)
    except Exception as e:
        print(f"-> [Предупреждение] Не удалось построить график: {e}")
            
    # Запись итогового текстового отчета в выходной файл
    print_divider()
    print(f"Сохранение результатов в отчет: {output_file}...")
    
    with open(output_file, "w", encoding="utf-8") as out:
        out.write("=== РЕЗУЛЬТАТЫ СИНТЕЗА ЦЕПЕЙ СИНХРОНИЗАЦИИ (CTS) ===\n")
        out.write(f"Статус валидации: {'УСПЕШНО' if is_valid else 'ОШИБКА НАЙДЕНА'}\n")
        out.write(f"Время работы алгоритма: {execution_time:.4f} сек.\n")
        out.write(f"Максимальная задержка: {max(final_delays.values()):.4f} нс\n")
        out.write(f"Минимальная задержка: {min(final_delays.values()):.4f} нс\n")
        out.write(f"Разброс задержек (Skew): {final_skew:.4f} нс\n")
        out.write(f"Целевой разброс (Skew Target): {opt_params.get('skew_target', 0.05)} нс\n")
        
        out.write("\n--- ЗАДЕРЖКИ ДО ТЕРМИНАЛОВ (SINKS) ---\n")
        # Ключ lambda x: int(x[0][1:]) извлекает числовую часть из ID (например, из 'S105' берет 105)
        # благодаря этому сортировка будет идти строго по возрастанию номеров
        sorted_sinks = sorted(final_delays.items(), key=lambda x: int(x[0][1:]) if x[0][1:].isdigit() else x[0])
        
        for s_id, delay in sorted_sinks:
            out.write(f"Терминал {s_id}: задержка = {delay:.4f} нс\n")

            
        out.write("\n--- ТОПОЛОГИЯ ДЕРЕВА (СПИСОК СОЕДИНЕНИЙ) ---\n")
        # Вспомогательная функция для дампа связей графа в файл
        def dump_topology(node):
            for child in node.children:
                out.write(
                    f"Узел {node.id} ({node.node_type}) [{node.x}, {node.y}] -> "
                    f"Узел {child.id} ({child.node_type}) [{child.x}, {child.y}] | "
                    f"Длина провода: {child.wire_length_to_parent:.2f}\n"
                )
                dump_topology(child)
        dump_topology(root_node)

    print("=== CTS КОМПИЛЯТОР УСПЕШНО ЗАВЕРШИЛ РАБОТУ ===")
    print_divider()

if __name__ == "__main__":
    main()
