#include <stdio.h>
#include "stm8l10x.h"

#define USART_BAUDRATE      230400

#define GPIO_BTN            GPIOC, GPIO_Pin_0

#define GPIO_LED_YELLOW     GPIOA, GPIO_Pin_2
#define GPIO_LED_RED        GPIOA, GPIO_Pin_3

#define GPIO_Si4463_nSEL    GPIOB, GPIO_Pin_0
#define GPIO_Si4463_GPIO0   GPIOB, GPIO_Pin_1
#define GPIO_Si4463_GPIO1   GPIOB, GPIO_Pin_2
#define GPIO_Si4463_IRQ     GPIOB, GPIO_Pin_3
#define GPIO_Si4463_SDN     GPIOD, GPIO_Pin_0

#define GPIO_SPI_SCK        GPIOB, GPIO_Pin_5
#define GPIO_SPI_MOSI       GPIOB, GPIO_Pin_6
#define GPIO_SPI_MISO       GPIOB, GPIO_Pin_7

#define GPIO_USART          GPIOC, GPIO_Pin_2 | GPIO_Pin_3
#define GPIO_USART_RX       GPIOC, GPIO_Pin_2
#define GPIO_USART_TX       GPIOC, GPIO_Pin_3

void Delay(uint32_t nCount) {
  while (nCount) {
    --nCount;
  }
}

static uint8_t USART_RecvByte(void) {
    while (!USART_GetFlagStatus(USART_FLAG_RXNE));
    return USART_ReceiveData8();
}

static void USART_SendByte(uint8_t byte) {
    while (!USART_GetFlagStatus(USART_FLAG_TXE));
    USART_SendData8(byte);
}

#define READ_CMD_BUFF 0x44
#define DUMMY_BYTE 0xFF

static void Si4463_Select(void) {
    GPIO_ResetBits(GPIO_Si4463_nSEL);
}

static void Si4463_Deselect(void) {
    GPIO_SetBits(GPIO_Si4463_nSEL);
}

static void Si4463_SendRequest(uint8_t *req, uint8_t len) {
    // send request
    for (uint8_t i = 0; i < len; ++i) {
        SPI_SendData(req[i]);
        while (!SPI_GetFlagStatus(SPI_SR_TXE));
    }

    // wait for last transmission
    while (SPI_GetFlagStatus(SPI_SR_BSY));

    // clear OVR flag
    SPI_ReceiveData();
    SPI_GetFlagStatus(SPI_FLAG_OVR);
}

static void Si4463_WaitCTS(void) {
    // GPIO1: CTS (POR default)
    while (!GPIO_ReadInputDataBit(GPIO_Si4463_GPIO1));
}

static void Si4463_ReadCmdBuff(void) {
    // send the 1st byte
    SPI_SendData(READ_CMD_BUFF);

    // recv the 1st byte and discard
    while (!SPI_GetFlagStatus(SPI_FLAG_RXNE));
    SPI_ReceiveData();

    // send the 2nd byte
    SPI_SendData(DUMMY_BYTE);

    // recv CTS and discard
    while (!SPI_GetFlagStatus(SPI_FLAG_RXNE));
    SPI_ReceiveData();
}

static void Si4463_RecvResponse(uint8_t *rsp, uint8_t rsp_len) {
    for (uint8_t i = 0; i < rsp_len; ++i) {
        SPI_SendData(DUMMY_BYTE);
        while (!SPI_GetFlagStatus(SPI_FLAG_RXNE));
        rsp[i] = SPI_ReceiveData();
    }
}

static void Si4463_Reset(void) {
    Delay(0x20000);
    GPIO_ResetBits(GPIO_Si4463_SDN);
    Delay(0x20000);
}

void main(void) {
    CLK_MasterPrescalerConfig(CLK_MasterPrescaler_HSIDiv1);

    CLK_PeripheralClockConfig(CLK_Peripheral_USART, ENABLE);
    GPIO_ExternalPullUpConfig(GPIO_USART, ENABLE);
    USART_Init(
        USART_BAUDRATE,
        USART_WordLength_8D,
        USART_StopBits_1,
        USART_Parity_No,
        USART_Mode_Tx | USART_Mode_Rx
    );

    CLK_PeripheralClockConfig(CLK_Peripheral_SPI, ENABLE);
    SPI_Init(
        SPI_FirstBit_MSB,
        SPI_BaudRatePrescaler_2,
        SPI_Mode_Master,
        SPI_CPOL_Low,
        SPI_CPHA_1Edge,
        SPI_Direction_2Lines_FullDuplex,
        SPI_NSS_Soft
    );
    SPI_Cmd(ENABLE);
    GPIO_Init(GPIO_SPI_SCK, GPIO_Mode_Out_PP_Low_Fast);
    GPIO_Init(GPIO_SPI_MOSI, GPIO_Mode_Out_PP_Low_Fast);
    GPIO_Init(GPIO_SPI_MISO, GPIO_Mode_In_PU_No_IT);
    GPIO_Init(GPIO_Si4463_SDN, GPIO_Mode_Out_PP_High_Fast);
    GPIO_Init(GPIO_Si4463_nSEL, GPIO_Mode_Out_PP_High_Fast);
    GPIO_Init(GPIO_Si4463_GPIO1, GPIO_Mode_In_PU_No_IT);

    Si4463_Reset();

    while (1) {
        uint8_t buf[256];
        uint8_t req_len;
        uint8_t rsp_len;

        // receive request
        req_len = USART_RecvByte();
        rsp_len = USART_RecvByte();
        for (uint8_t i = 0; i < req_len; ++i) {
            buf[i] = USART_RecvByte();
        }

        // special command
        if (req_len == 0) {
            switch (rsp_len) {
                case 0: { // identify
                    GPIO_Init(GPIO_LED_YELLOW, GPIO_Mode_Out_OD_HiZ_Fast);
                    for (uint8_t i = 0; i < 6; ++i) {
                        GPIO_ToggleBits(GPIO_LED_YELLOW);
                        Delay(0x40000);
                    }
                    break;
                }
                default: {
                    Si4463_Reset();
                    break;
                }
            }
            USART_SendByte(DUMMY_BYTE);
            continue;
        }

        // forward to Si4463 via SPI
        Si4463_Select();
        Si4463_SendRequest(buf, req_len);
        switch (buf[0]) {
            case 0x77: // READ_RX_FIFO
            case 0x66: // WRITE_TX_FIFO
            case 0x44: // READ_CMD_BUFF
            case 0x50: // FRR_A_READ
            case 0x51: // FRR_B_READ
            case 0x53: // FRR_C_READ
            case 0x57: // FRR_D_READ
                break;
            default:
                Si4463_Deselect();
                Si4463_WaitCTS();
                if (rsp_len == 0) goto sync;
                Si4463_Select();
                Si4463_ReadCmdBuff();
                break;
        }
        Si4463_RecvResponse(buf, rsp_len);
        Si4463_Deselect();

        // send response
        if (rsp_len) {
            for (uint8_t i = 0; i < rsp_len; ++i) {
                USART_SendByte(buf[i]);
            }
        } else {
sync:
            USART_SendByte(DUMMY_BYTE);
        }
    }
}
