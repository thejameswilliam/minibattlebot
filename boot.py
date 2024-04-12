from machine import ADC, Pin, PWM
import time

# Joystick setup
adc_x = ADC(Pin(35))
adc_y = ADC(Pin(34))
adc_x.atten(ADC.ATTN_11DB)  # 0-3.3V
adc_y.atten(ADC.ATTN_11DB)  # 0-3.3V

# Motor A setup
motor_a_in1 = Pin(17, Pin.OUT)
motor_a_in2 = Pin(16, Pin.OUT)
motor_a_pwm = PWM(Pin(15), freq=1000)

# Motor B setup
motor_b_in1 = Pin(19, Pin.OUT)
motor_b_in2 = Pin(18, Pin.OUT)
motor_b_pwm = PWM(Pin(13), freq=1000)

def map_value(x, in_min, in_max, out_min, out_max):
    return (x - in_min) * (out_max - out_min) // (in_max - in_min) + out_min

def motor_control(motor_in1, motor_in2, pwm, speed):
    if speed > 0:
        motor_in1.value(1)
        motor_in2.value(0)
    elif speed < 0:
        motor_in1.value(0)
        motor_in2.value(1)
    else:
        motor_in1.value(0)
        motor_in2.value(0)
    pwm.duty(abs(speed))

def get_joystick_values():
    x_value = adc_x.read()
    y_value = adc_y.read()
    # Convert 0-4095 -> -1023 to 1023 (full reverse to full forward)
    x_mapped = map_value(x_value, 0, 4095, -1023, 1023)
    y_mapped = map_value(y_value, 0, 4095, -1023, 1023)


    if abs(x_mapped) < 100:
        x_mapped = 0

    if abs(y_mapped) < 100:
        y_mapped = 0

    return x_mapped, y_mapped

while True:
    x, y = get_joystick_values()
    
    # Basic forward/reverse control
    base_speed = y

    print("Base Speed: ", base_speed)
    
    # Turning control: modify base_speed based on x
    motor_a_speed = base_speed + x
    motor_b_speed = base_speed - x
    
    # Ensure speeds do not exceed max values
    motor_a_speed = min(max(motor_a_speed, -1023), 1023)
    motor_b_speed = min(max(motor_b_speed, -1023), 1023)
    
    # Apply speeds to motors
    motor_control(motor_a_in1, motor_a_in2, motor_a_pwm, motor_a_speed)
    motor_control(motor_b_in1, motor_b_in2, motor_b_pwm, motor_b_speed)
    
    time.sleep(0.1)