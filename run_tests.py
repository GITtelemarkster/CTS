import os
import shutil
import subprocess
import time

def run_team_pipeline():
    # Проверяем наличие сгенерированных тестов
    test_cases = ["test_easy.json", "test_medium.json", "test_hard.json", "test_stress.json"]
    
    print("=" * 60)
    print("ЗАПУСК КОМАНДНОГО ТЕСТИРОВАНИЯ CTS ПРОЕКТА")
    print("=" * 60)

    # 1. Сначала генерируем свежие тесты
    print("[ШАГ 1] Генерация тестовых наборов...")
    subprocess.run(["python", "tests/test_generator.py"])
    
    os.makedirs("data", exist_ok=True)
    os.makedirs("results", exist_ok=True)

    print("\n[ШАГ 2] Прогон конфигураций через компилятор...")
    
    # 2. Перебираем тесты
    for case in test_cases:
        source_path = os.path.join("tests", case)
        dest_path = os.path.join("data", "input.json")
        
        if not os.path.exists(source_path):
            print(f"Файл {source_path} не найден. Пропуск.")
            continue
            
        print(f"\nТестируем конфигурацию: {case}...")
        
        # Копируем тест во входную папку компилятора
        shutil.copy(source_path, dest_path)
        
        # Запускаем наш основной компилятор
        start = time.time()
        result = subprocess.run(["python", "source/main.py"], capture_output=True, text=True)
        duration = time.time() - start
        
        # Бэкапим результаты для анализа
        case_name = case.replace(".json", "")
        if os.path.exists("data/output.txt"):
            shutil.copy("data/output.txt", f"results/output_{case_name}.txt")
        if os.path.exists("data/clock_tree.png"):
            shutil.copy("data/clock_tree.png", f"results/plot_{case_name}.png")
            
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
