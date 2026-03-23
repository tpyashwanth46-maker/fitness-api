import time

print("\n===== FITNESS AI PIPELINE STARTED =====\n")

start = time.time()

print("STEP 1: Running Calories Model Training...")
import src.train_model
print("Calories Model Training Completed\n")

print("STEP 2: Running Biological Age Model...")
import src.bio_age_model
print("Biological Age Model Completed\n")

print("STEP 3: Starting Fitness AI Voice System...")
import src.fitness_ai_system
print("Voice System Started\n")

end = time.time()

print("===== PIPELINE COMPLETED =====")
print("Total Execution Time:", round(end - start, 2), "seconds\n")
