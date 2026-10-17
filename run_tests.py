import os
import subprocess
import time

def run_team_pipeline():
    # Список тест-кейсов (находятся в корне или в папке tests)
    test_cases = ["test_easy.json", "test_medium.json", "test_hard.json", "test_stress.json"]
    
    print("=" * 60)
    print("ЗАПУСК КОМАНДНОГО ТЕСТИРОВАНИЯ CTS ПРОЕКТА")
    print("=" * 60)

    # 1. Сначала генерируем свежие тесты
    print("[ШАГ 1] Генерация тестовых наборов...")
    # Используем os.path.join для кроссплатформенности путей
    generator_path = os.path.join("tests", "test_generator.py")
    subprocess.run(["python", generator_path])
    
    # Создаем только папку results, папку data больше не трогаем
    os.makedirs("results", exist_ok=True)

    print("\n[ШАГ 2] Прогон конфигураций через компилятор...")
    
    # 2. Перебираем тесты
    for case in test_cases:
        # Корректный путь к исходному тесту (внутри папки tests)
        source_path = os.path.join("tests", case)
        
        if not os.path.exists(source_path):
            print(f"Файл {source_path} не найден. Пропуск.")
            continue
            
        print(f"\nТестируем конфигурацию: {case}...")
        
        case_name = case.replace(".json", "")
        
        # Запускаем основной компилятор, передавая ему параметры напрямую.
        # Теперь source/main.py должен принимать аргументы: --input и --output_dir
        start = time.time()
        result = subprocess.run([
            "python", "source/main.py", 
            "--input", source_path, 
            "--output_dir", "results",
            "--name", case_name
        ], capture_output=True, text=True)
        
        duration = time.time() - start
            
        if result.returncode == 0:
            print(f"-> УСПЕХ: {case} обработан за {duration:.4f} сек.")
        else:
            print(f"-> ОШИБКА при обработке {case}!")
            print(result.stderr)

    print("\n" + "=" * 60)
    print("Тестирование завершено! Все отчеты и графики сохранены в папку /results")
    print("=" * 60)

if __name__ == "__main__":
    run_team_pipeline()
