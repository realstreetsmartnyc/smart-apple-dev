extends Node2D

# Entry point. Runs once when the scene loads.
func _ready() -> void:
    print("Hello from {{NAME}}!")
    $Label.text = "Hello from {{NAME}}!"
