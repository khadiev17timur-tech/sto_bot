from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    select_date = State()
    select_time = State()
    select_service = State()
    enter_service_description = State()  # только для услуги "Другое"
    enter_name = State()
    enter_phone = State()
    enter_car_brand = State()
    enter_car_model = State()
    enter_license_plate = State()
    select_lowering = State()  # только для услуги "Развал-схождение"
    enter_lowering_custom = State()
    enter_comment = State()
    confirmation = State()
