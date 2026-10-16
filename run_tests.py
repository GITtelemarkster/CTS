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
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: принудительно удаляем старый input, если он есть
        if os.path.exists(dest_path):
            os.remove(dest_path)
            time.sleep(0.05)  # Пауза, чтобы ОС успела освободить дескриптор файла
        
        # Копируем новый тест во входную папку компилятора
        shutil.copy(source_path, dest_path)
        time.sleep(0.05)  # Гарантируем физическую запись файла на диск
        
        # Настройка окружения (PYTHONPATH) для корректных импортов внутри папки source
        current_env = os.environ.copy()
        source_dir = os.path.abspath("source") 
        current_env["PYTHONPATH"] = source_dir + os.pathsep + current_env.get("PYTHONPATH", "")

        # Запускаем основной компилятор с проброшенным путем окружения
        start = time.time()
        result = subprocess.run(["python", "source/main.py"], capture_output=True, text=True, env=current_env)
        duration = time.time() - start
        
        # Бэкапим результаты под уникальными именами
        case_name = case.replace(".json", "")
        
        # Кроссплатформенное копирование текстового отчета через os.path.join
        src_out = os.path.join("data", "output.txt")
        dst_out = os.path.join("results", f"output_{case_name}.txt")
        if os.path.exists(src_out):
            shutil.copy(src_out, dst_out)
            
        # БЕЗОПАСНОЕ копирование графика (защита от падения на стресс-тестах)
        src_img = os.path.join("data", "clock_tree.png")
        dst_img = os.path.join("results", f"plot_{case_name}.png")
        if os.path.exists(src_img):
            shutil.copy(src_img, dst_img)
            
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
