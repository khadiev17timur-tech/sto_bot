from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    # Общий выбор даты в календаре — конкретное действие хранится в FSM data (ключ "admin_mode")
    choose_date = State()

    add_slot_enter_time = State()
    remove_slot_pick = State()

    cancel_booking_pick = State()
    cancel_booking_confirm = State()

    close_day_confirm = State()
    reopen_day_confirm = State()
    add_working_day_confirm = State()
    remove_working_day_confirm = State()
