import os
import subprocess
import time
import shutil
import argparse  # Добавлен модуль для обработки аргументов командной строки

def run_team_pipeline():
    # Настройка парсера аргументов командной строки
    parser = argparse.ArgumentParser(description="CTS Pipeline Runner")
    parser.add_argument(
        "--case", 
        type=str, 
        default=None, 
        help="Имя конкретного json-файла для теста (например, test_easy.json). Если не указан, тестируются все файлы в папке tests."
    )
    args = parser.parse_parser = parser.parse_args()

    tests_dir = "tests"
    results_dir = "results"

    # Определение списка тест-кейсов
    if args.case:
        # Если передан конкретный файл, берем только его
        test_cases = [args.case]
    else:
        # ИЗМЕНЕНО: По умолчанию автоматически собираем ВСЕ .json файлы в папке tests
        if os.path.exists(tests_dir):
            test_cases = [f for f in os.listdir(tests_dir) if f.endswith(".json")]
            # Сортируем для красоты вывода (easy -> medium -> hard -> stress)
            test_cases.sort()
        else:
            test_cases = []

    print("=" * 60)
    print("ЗАПУСК КОМАНДНОГО ТЕСТИРОВАНИЯ CTS ПРОЕКТА")
    print("=" * 60)
    print(f"Найдено файлов для обработки: {len(test_cases)}")

    if not test_cases:
        print(f"[Ошибка] Не найдено .json конфигураций для тестирования в папке {tests_dir}!")
        return

    # Очищаем старые результаты перед запуском, если папка существует
    if os.path.exists(results_dir):
        print(f"[ОЧИСТКА] Удаление старых файлов из папки {results_dir}...")
        for filename in os.listdir(results_dir):
            file_path = os.path.join(results_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"Не удалось удалить {file_path}. Возможно, файл открыт в другой программе. Ошибка: {e}")
    
    # Создаем чистую папку results
    os.makedirs(results_dir, exist_ok=True)

    print("\n[ЗАПУСК] Прогон конфигураций через компилятор...")
    
    # Перебираем тесты
    for case in test_cases:
        source_path = os.path.join(tests_dir, case)
        
        if not os.path.exists(source_path):
            print(f"Файл {source_path} не найден. Пропуск.")
            continue
            
        print(f"\nТестируем конфигурацию: {case}...")
        
        case_name = case.replace(".json", "")
        
        # Запускаем основной компилятор, передавая ему параметры напрямую.
        start = time.time()
        result = subprocess.run([
            "python", "source/main.py", 
            "--input", source_path, 
            "--output_dir", results_dir,
            "--name", case_name
        ], capture_output=True, text=True)
        
        duration = time.time() - start
            
        if result.returncode == 0:
            print(f"-> УСПЕХ: {case} обработан за {duration:.4f} сек.")
        else:
            print(f"-> ОШИБКА при обработке {case}!")
            print(result.stderr)

    print("\n" + "=" * 60)
    print(f"Тестирование завершено! Все отчеты и графики сохранены в папку /{results_dir}")
    print("=" * 60)

if __name__ == "__main__":
    run_team_pipeline()
