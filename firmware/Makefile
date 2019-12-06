CC=sdcc
CFLAGS=-mstm8 --Werror

TARGET=main
DEPENDENCY=clk gpio spi usart
STM8FLASH_FLAGS=-c stlinkv2 -p 'stm8l101?3'

all: $(TARGET)

clean:
	rm -f *.asm *.cdb *.ihx *.lk *.lst *.map *.rel *.rst *.sym

flash: $(TARGET)
	stm8flash $(STM8FLASH_FLAGS) -w main.ihx

.PHONY: all clean flash $(TARGET)

define DEPENDENCY_TEMPLATE =
stm8l10x_$(1).rel: stm8l10x_$(1).c
	$$(CC) $$(CFLAGS) -c $$^
endef

# FIXME: incomplete dependency for header files
$(foreach dep,$(DEPENDENCY),$(eval $(call DEPENDENCY_TEMPLATE,$(dep))))

$(TARGET): $(TARGET).ihx
$(TARGET).ihx: $(TARGET).c $(foreach dep,$(DEPENDENCY),stm8l10x_$(dep).rel)
	$(CC) $(CFLAGS) $^
