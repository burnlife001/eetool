{
  "chip_name": "MM32F0140",
  "source_pdf": "DS_MM32F0140_EN.pdf",
  "packages": [
    "LQFP48",
    "LQFP32",
    "QFN325x5 mm2",
    "QFN324x4 mm2",
    "TSSOP20"
  ],
  "ports": [
    "PA",
    "PB",
    "PC",
    "PD"
  ],
  "pins": [
    {
      "name": "NC",
      "type": "",
      "io_level": "",
      "main_function": "",
      "multiplex_functions": [],
      "additional_functions": [],
      "packages": {
        "LQFP48": 1,
        "LQFP32": null,
        "QFN325x5 mm2": null,
        "QFN324x4 mm2": null,
        "TSSOP20": null
      },
      "alternate_functions": {}
    },
    {
      "name": "PC13",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PC13",
      "multiplex_functions": [
        "TIM2_CH1"
      ],
      "additional_functions": [],
      "packages": {
        "LQFP48": 2,
        "LQFP32": null,
        "QFN325x5 mm2": null,
        "QFN324x4 mm2": null,
        "TSSOP20": null
      },
      "alternate_functions": {
        "AF0": null,
        "AF1": null,
        "AF2": null,
        "AF3": null,
        "AF4": null,
        "AF5": null,
        "AF6": "TIM2_CH1",
        "AF7": null,
        "AF8": null
      }
    },
    {
      "name": "PC14",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PC14",
      "multiplex_functions": [
        "TIM2_CH2"
      ],
      "additional_functions": [],
      "packages": {
        "LQFP48": 3,
        "LQFP32": null,
        "QFN325x5 mm2": null,
        "QFN324x4 mm2": null,
        "TSSOP20": null
      },
      "alternate_functions": {
        "AF0": null,
        "AF1": null,
        "AF2": null,
        "AF3": null,
        "AF4": null,
        "AF5": null,
        "AF6": "TIM2_CH2",
        "AF7": null,
        "AF8": null
      }
    },
    {
      "name": "PC15",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PC15",
      "multiplex_functions": [
        "TIM2_CH3"
      ],
      "additional_functions": [],
      "packages": {
        "LQFP48": 4,
        "LQFP32": null,
        "QFN325x5 mm2": null,
        "QFN324x4 mm2": null,
        "TSSOP20": null
      },
      "alternate_functions": {
        "AF0": null,
        "AF1": null,
        "AF2": null,
        "AF3": null,
        "AF4": null,
        "AF5": null,
        "AF6": "TIM2_CH3",
        "AF7": null,
        "AF8": null
      }
    },
    {
      "name": "PD0 OSC_IN",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PD0",
      "multiplex_functions": [
        "UART3_TX",
        "I2C_SDA"
      ],
      "additional_functions": [],
      "packages": {
        "LQFP48": 5,
        "LQFP32": 2,
        "QFN325x5 mm2": 2,
        "QFN324x4 mm2": 2,
        "TSSOP20": 2
      },
      "alternate_functions": {
        "AF0": "UART3_TX",
        "AF1": "I2C_SDA",
        "AF2": null,
        "AF3": null,
        "AF4": null,
        "AF5": null,
        "AF6": null,
        "AF7": null,
        "AF8": null
      }
    },
    {
      "name": "PD1 OSC_OUT",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PD1",
      "multiplex_functions": [
        "UART3_RX",
        "I2C_SCL"
      ],
      "additional_functions": [],
      "packages": {
        "LQFP48": 6,
        "LQFP32": 3,
        "QFN325x5 mm2": 3,
        "QFN324x4 mm2": 3,
        "TSSOP20": 3
      },
      "alternate_functions": {
        "AF0": "UART3_RX",
        "AF1": "I2C_SCL",
        "AF2": null,
        "AF3": null,
        "AF4": null,
        "AF5": null,
        "AF6": null,
        "AF7": null,
        "AF8": null
      }
    },
    {
      "name": "NRST1",
      "type": "I/O",
      "io_level": "",
      "main_function": "NRST1",
      "multiplex_functions": [],
      "additional_functions": [],
      "packages": {
        "LQFP48": 7,
        "LQFP32": 4,
        "QFN325x5 mm2": 4,
        "QFN324x4 mm2": 4,
        "TSSOP20": 4
      },
      "alternate_functions": {}
    },
    {
      "name": "VSS",
      "type": "S",
      "io_level": "",
      "main_function": "VSS",
      "multiplex_functions": [],
      "additional_functions": [],
      "packages": {
        "LQFP48": 8,
        "LQFP32": null,
        "QFN325x5 mm2": null,
        "QFN324x4 mm2": null,
        "TSSOP20": null
      },
      "alternate_functions": {}
    },
    {
      "name": "VDDA",
      "type": "S",
      "io_level": "",
      "main_function": "VDDA",
      "multiplex_functions": [],
      "additional_functions": [],
      "packages": {
        "LQFP48": 9,
        "LQFP32": 5,
        "QFN325x5 mm2": 5,
        "QFN324x4 mm2": 1,
        "TSSOP20": 5
      },
      "alternate_functions": {}
    },
    {
      "name": "PA0 WKUP",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PA0",
      "multiplex_functions": [
        "UART2_CTS",
        "TIM2_CH1",
        "TIM2_ETR",
        "SPI2_NSS",
        "I2S2_WS",
        "TIM2_CH3",
        "COMP1_OUT"
      ],
      "additional_functions": [
        "ADC1_VIN[0]"
      ],
      "packages": {
        "LQFP48": 10,
        "LQFP32": 6,
        "QFN325x5 mm2": 6,
        "QFN324x4 mm2": 5,
        "TSSOP20": 6
      },
      "alternate_functions": {
        "AF0": null,
        "AF1": "UART2_CTS",
        "AF2": "TIM2_CH1/TIM2_ETR",
        "AF3": "SPI2_NSS/I2S2_WS",
        "AF4": "TIM2_CH3",
        "AF5": null,
        "AF6": null,
        "AF7": "COMP1_OUT",
        "AF8": null
      }
    },
    {
      "name": "PA1",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PA1",
      "multiplex_functions": [
        "UART2_RTS",
        "TIM2_CH2"
      ],
      "additional_functions": [
        "ADC1_VIN[1]",
        "COMP_INP[0]"
      ],
      "packages": {
        "LQFP48": 11,
        "LQFP32": 7,
        "QFN325x5 mm2": 7,
        "QFN324x4 mm2": 6,
        "TSSOP20": 7
      },
      "alternate_functions": {
        "AF0": null,
        "AF1": "UART2_RTS",
        "AF2": "TIM2_CH2",
        "AF3": null,
        "AF4": null,
        "AF5": null,
        "AF6": null,
        "AF7": null,
        "AF8": null
      }
    },
    {
      "name": "PA2",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PA2",
      "multiplex_functions": [
        "UART2_TX",
        "TIM2_CH3",
        "SPI2_NSS",
        "I2S2_WS"
      ],
      "additional_functions": [
        "ADC1_VIN[2]",
        "COMP_INP[1]"
      ],
      "packages": {
        "LQFP48": 12,
        "LQFP32": 8,
        "QFN325x5 mm2": 8,
        "QFN324x4 mm2": 7,
        "TSSOP20": 8
      },
      "alternate_functions": {
        "AF0": null,
        "AF1": "UART2_TX",
        "AF2": "TIM2_CH3",
        "AF3": "SPI2_NSS/I2S2_WS",
        "AF4": null,
        "AF5": null,
        "AF6": null,
        "AF7": null,
        "AF8": null
      }
    },
    {
      "name": "PA3",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PA3",
      "multiplex_functions": [
        "UART2_RX",
        "TIM2_CH4"
      ],
      "additional_functions": [
        "ADC1_VIN[3]",
        "COMP_INP[2]"
      ],
      "packages": {
        "LQFP48": 13,
        "LQFP32": 9,
        "QFN325x5 mm2": 9,
        "QFN324x4 mm2": 8,
        "TSSOP20": 9
      },
      "alternate_functions": {
        "AF0": null,
        "AF1": "UART2_RX",
        "AF2": "TIM2_CH4",
        "AF3": null,
        "AF4": null,
        "AF5": null,
        "AF6": null,
        "AF7": null,
        "AF8": null
      }
    },
    {
      "name": "PA4",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PA4",
      "multiplex_functions": [
        "SPI1_NSS",
        "I2S1_WS",
        "TIM1_BKIN",
        "TIM14_CH1",
        "I2C_SDA"
      ],
      "additional_functions": [
        "ADC1_VIN[4]",
        "COMP_INP[3]"
      ],
      "packages": {
        "LQFP48": 14,
        "LQFP32": 10,
        "QFN325x5 mm2": 10,
        "QFN324x4 mm2": 9,
        "TSSOP20": 10
      },
      "alternate_functions": {
        "AF0": "SPI1_NSS/I2S1_WS",
        "AF1": null,
        "AF2": null,
        "AF3": "TIM1_BKIN",
        "AF4": "TIM14_CH1",
        "AF5": "I2C_SDA",
        "AF6": null,
        "AF7": null,
        "AF8": null
      }
    },
    {
      "name": "PA5",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PA5",
      "multiplex_functions": [
        "SPI1_SCK",
        "I2S1_CK",
        "TIM2_CH1",
        "TIM2_ETR",
        "TIM1_ETR",
        "I2C_SCL",
        "TIM1_CH3N"
      ],
      "additional_functions": [
        "ADC1_VIN[5]",
        "COMP_INM[0]"
      ],
      "packages": {
        "LQFP48": 15,
        "LQFP32": 11,
        "QFN325x5 mm2": 11,
        "QFN324x4 mm2": 10,
        "TSSOP20": 11
      },
      "alternate_functions": {
        "AF0": "SPI1_SCK/I2S1_CK",
        "AF1": null,
        "AF2": "TIM2_CH1/TIM2_ETR",
        "AF3": "TIM1_ETR",
        "AF4": null,
        "AF5": "I2C_SCL",
        "AF6": "TIM1_CH3N",
        "AF7": null,
        "AF8": null
      }
    },
    {
      "name": "PA6",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PA6",
      "multiplex_functions": [
        "SPI1_MISO",
        "I2S1_MCK",
        "TIM3_CH1",
        "TIM1_BKIN",
        "UART2_RX",
        "TIM1_ETR",
        "TIM16_CH1",
        "TIM1_CH3",
        "COMP1_OUT"
      ],
      "additional_functions": [
        "ADC1_VIN[6]",
        "COMP_INM[1]"
      ],
      "packages": {
        "LQFP48": 16,
        "LQFP32": 12,
        "QFN325x5 mm2": 12,
        "QFN324x4 mm2": 11,
        "TSSOP20": 12
      },
      "alternate_functions": {
        "AF0": "SPI1_MISO/I2S1_MCK",
        "AF1": "TIM3_CH1",
        "AF2": "TIM1_BKIN",
        "AF3": "UART2_RX",
        "AF4": "TIM1_ETR",
        "AF5": "TIM16_CH1",
        "AF6": "TIM1_CH3",
        "AF7": "COMP1_OUT",
        "AF8": null
      }
    },
    {
      "name": "PA7",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PA7",
      "multiplex_functions": [
        "SPI1_MOSI",
        "I2S1_SD",
        "TIM3_CH2",
        "TIM1_CH1N",
        "TIM14_CH1",
        "TIM17_CH1",
        "TIM1_CH2N",
        "TIM1_CH3N"
      ],
      "additional_functions": [
        "ADC1_VIN[7]",
        "COMP_INM[2]"
      ],
      "packages": {
        "LQFP48": 17,
        "LQFP32": 13,
        "QFN325x5 mm2": 13,
        "QFN324x4 mm2": 12,
        "TSSOP20": 13
      },
      "alternate_functions": {
        "AF0": "SPI1_MOSI/I2S1_SD",
        "AF1": "TIM3_CH2",
        "AF2": "TIM1_CH1N",
        "AF3": null,
        "AF4": "TIM14_CH1",
        "AF5": "TIM17_CH1",
        "AF6": "TIM1_CH2N",
        "AF7": "TIM1_CH3N",
        "AF8": null
      }
    },
    {
      "name": "PB0",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PB0",
      "multiplex_functions": [
        "TIM3_CH3",
        "TIM1_CH2N",
        "TIM1_CH1N",
        "TIM1_CH3"
      ],
      "additional_functions": [
        "ADC1_VIN[8]"
      ],
      "packages": {
        "LQFP48": 18,
        "LQFP32": 14,
        "QFN325x5 mm2": 14,
        "QFN324x4 mm2": 13,
        "TSSOP20": null
      },
      "alternate_functions": {
        "AF0": null,
        "AF1": "TIM3_CH3",
        "AF2": "TIM1_CH2N",
        "AF3": "TIM1_CH1N",
        "AF4": "TIM1_CH3",
        "AF5": null,
        "AF6": null,
        "AF7": null,
        "AF8": null
      }
    },
    {
      "name": "PB1",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PB1",
      "multiplex_functions": [
        "TIM14_CH1",
        "TIM3_CH4",
        "TIM1_CH3N",
        "TIM1_CH4",
        "TIM1_CH2N",
        "MCO",
        "TIM1_CH2",
        "TIM1_CH1N"
      ],
      "additional_functions": [
        "ADC1_VIN[9]"
      ],
      "packages": {
        "LQFP48": 19,
        "LQFP32": 15,
        "QFN325x5 mm2": 15,
        "QFN324x4 mm2": 14,
        "TSSOP20": 14
      },
      "alternate_functions": {
        "AF0": "TIM14_CH1",
        "AF1": "TIM3_CH4",
        "AF2": "TIM1_CH3N",
        "AF3": "TIM1_CH4",
        "AF4": "TIM1_CH2N",
        "AF5": "MCO",
        "AF6": "TIM1_CH2",
        "AF7": "TIM1_CH1N",
        "AF8": null
      }
    },
    {
      "name": "PB2",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PB2",
      "multiplex_functions": [],
      "additional_functions": [],
      "packages": {
        "LQFP48": 20,
        "LQFP32": null,
        "QFN325x5 mm2": 16,
        "QFN324x4 mm2": 15,
        "TSSOP20": null
      },
      "alternate_functions": {
        "AF0": null,
        "AF1": null,
        "AF2": null,
        "AF3": null,
        "AF4": null,
        "AF5": null,
        "AF6": null,
        "AF7": null,
        "AF8": null
      }
    },
    {
      "name": "PB10",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PB10",
      "multiplex_functions": [
        "I2C_SCL",
        "TIM2_CH3",
        "UART3_TX",
        "SPI2_SCK",
        "I2S2_CK"
      ],
      "additional_functions": [],
      "packages": {
        "LQFP48": 21,
        "LQFP32": null,
        "QFN325x5 mm2": null,
        "QFN324x4 mm2": null,
        "TSSOP20": null
      },
      "alternate_functions": {
        "AF0": null,
        "AF1": "I2C_SCL",
        "AF2": "TIM2_CH3",
        "AF3": null,
        "AF4": "UART3_TX",
        "AF5": "SPI2_SCK/I2S2_CK",
        "AF6": null,
        "AF7": null,
        "AF8": null
      }
    },
    {
      "name": "PB11",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PB11",
      "multiplex_functions": [
        "I2C_SDA",
        "TIM2_CH4",
        "UART3_RX"
      ],
      "additional_functions": [],
      "packages": {
        "LQFP48": 22,
        "LQFP32": null,
        "QFN325x5 mm2": null,
        "QFN324x4 mm2": null,
        "TSSOP20": null
      },
      "alternate_functions": {
        "AF0": null,
        "AF1": "I2C_SDA",
        "AF2": "TIM2_CH4",
        "AF3": null,
        "AF4": "UART3_RX",
        "AF5": null,
        "AF6": null,
        "AF7": null,
        "AF8": null
      }
    },
    {
      "name": "VSS",
      "type": "S",
      "io_level": "",
      "main_function": "VSS",
      "multiplex_functions": [],
      "additional_functions": [],
      "packages": {
        "LQFP48": 23,
        "LQFP32": 16,
        "QFN325x5 mm2": null,
        "QFN324x4 mm2": null,
        "TSSOP20": 15
      },
      "alternate_functions": {}
    },
    {
      "name": "VDD",
      "type": "S",
      "io_level": "",
      "main_function": "VDD",
      "multiplex_functions": [],
      "additional_functions": [],
      "packages": {
        "LQFP48": 24,
        "LQFP32": 17,
        "QFN325x5 mm2": 17,
        "QFN324x4 mm2": null,
        "TSSOP20": 16
      },
      "alternate_functions": {}
    },
    {
      "name": "PB12",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PB12",
      "multiplex_functions": [
        "SPI2_NSS",
        "I2S2_WS",
        "SPI2_SCK",
        "I2S2_CK",
        "TIM1_BKIN",
        "SPI2_MOSI",
        "I2S2_SD",
        "SPI2_MISO",
        "I2S2_MCK"
      ],
      "additional_functions": [],
      "packages": {
        "LQFP48": 25,
        "LQFP32": null,
        "QFN325x5 mm2": null,
        "QFN324x4 mm2": null,
        "TSSOP20": null
      },
      "alternate_functions": {
        "AF0": "SPI2_NSS/I2S2_WS",
        "AF1": "SPI2_SCK/I2S2_CK",
        "AF2": "TIM1_BKIN",
        "AF3": "SPI2_MOSI/I2S2_SD",
        "AF4": "SPI2_MISO/I2S2_MCK",
        "AF5": null,
        "AF6": null,
        "AF7": null,
        "AF8": null
      }
    },
    {
      "name": "PB13",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PB13",
      "multiplex_functions": [
        "SPI2_SCK",
        "I2S2_CK",
        "SPI2_MISO",
        "I2S2_MCK",
        "TIM1_CH1N",
        "SPI2_NSS",
        "I2S2_WS",
        "SPI2_MOSI",
        "I2S2_SD",
        "I2C_SCL",
        "TIM1_CH3N",
        "TIM2_CH1",
        "UART3_CTS"
      ],
      "additional_functions": [],
      "packages": {
        "LQFP48": 26,
        "LQFP32": null,
        "QFN325x5 mm2": null,
        "QFN324x4 mm2": 16,
        "TSSOP20": null
      },
      "alternate_functions": {
        "AF0": "SPI2_SCK/I2S2_CK",
        "AF1": "SPI2_MISO/I2S2_MCK",
        "AF2": "TIM1_CH1N",
        "AF3": "SPI2_NSS/I2S2_WS",
        "AF4": "SPI2_MOSI/I2S2_SD",
        "AF5": "I2C_SCL",
        "AF6": "TIM1_CH3N",
        "AF7": "TIM2_CH1",
        "AF8": "UART3_CTS"
      }
    },
    {
      "name": "PB14",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PB14",
      "multiplex_functions": [
        "SPI2_MISO",
        "I2S2_MCK",
        "SPI2_MOSI",
        "I2S2_SD",
        "TIM1_CH2N",
        "SPI2_SCK",
        "I2S2_CK",
        "SPI2_NSS",
        "I2S2_WS",
        "I2C_SDA",
        "TIM1_CH3",
        "TIM1_CH1",
        "UART3_RTS"
      ],
      "additional_functions": [],
      "packages": {
        "LQFP48": 27,
        "LQFP32": null,
        "QFN325x5 mm2": null,
        "QFN324x4 mm2": 17,
        "TSSOP20": null
      },
      "alternate_functions": {
        "AF0": "SPI2_MISO/I2S2_MCK",
        "AF1": "SPI2_MOSI/I2S2_SD",
        "AF2": "TIM1_CH2N",
        "AF3": "SPI2_SCK/I2S2_CK",
        "AF4": "SPI2_NSS/I2S2_WS",
        "AF5": "I2C_SDA",
        "AF6": "TIM1_CH3",
        "AF7": "TIM1_CH1",
        "AF8": "UART3_RTS"
      }
    },
    {
      "name": "PB15",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PB15",
      "multiplex_functions": [
        "SPI2_MOSI",
        "I2S2_SD",
        "SPI2_NSS",
        "I2S2_WS",
        "TIM1_CH3N",
        "SPI2_MISO",
        "I2S2_MCK",
        "SPI2_SCK",
        "I2S2_CK",
        "TIM1_CH2N",
        "TIM1_CH2"
      ],
      "additional_functions": [],
      "packages": {
        "LQFP48": 28,
        "LQFP32": null,
        "QFN325x5 mm2": null,
        "QFN324x4 mm2": null,
        "TSSOP20": null
      },
      "alternate_functions": {
        "AF0": "SPI2_MOSI/I2S2_SD",
        "AF1": "SPI2_NSS/I2S2_WS",
        "AF2": "TIM1_CH3N",
        "AF3": "SPI2_MISO/I2S2_MCK",
        "AF4": "SPI2_SCK/I2S2_CK",
        "AF5": null,
        "AF6": "TIM1_CH2N",
        "AF7": "TIM1_CH2",
        "AF8": null
      }
    },
    {
      "name": "PA8",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PA8",
      "multiplex_functions": [
        "MCO",
        "TIM1_CH1",
        "TIM1_CH2",
        "TIM1_CH3"
      ],
      "additional_functions": [],
      "packages": {
        "LQFP48": 29,
        "LQFP32": 18,
        "QFN325x5 mm2": 18,
        "QFN324x4 mm2": 18,
        "TSSOP20": null
      },
      "alternate_functions": {
        "AF0": "MCO",
        "AF1": null,
        "AF2": "TIM1_CH1",
        "AF3": null,
        "AF4": null,
        "AF5": null,
        "AF6": "TIM1_CH2",
        "AF7": "TIM1_CH3",
        "AF8": null
      }
    },
    {
      "name": "PA9",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PA9",
      "multiplex_functions": [
        "UART1_TX",
        "TIM1_CH2",
        "UART1_RX",
        "I2C_SCL",
        "MCO",
        "TIM1_CH1N",
        "TIM1_CH4",
        "CAN_RX"
      ],
      "additional_functions": [],
      "packages": {
        "LQFP48": 30,
        "LQFP32": 19,
        "QFN325x5 mm2": 19,
        "QFN324x4 mm2": 19,
        "TSSOP20": 17
      },
      "alternate_functions": {
        "AF0": null,
        "AF1": "UART1_TX",
        "AF2": "TIM1_CH2",
        "AF3": "UART1_RX",
        "AF4": "I2C_SCL",
        "AF5": "MCO",
        "AF6": "TIM1_CH1N",
        "AF7": "TIM1_CH4",
        "AF8": "CAN_RX"
      }
    },
    {
      "name": "PA10",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PA10",
      "multiplex_functions": [
        "TIM17_BKIN",
        "UART1_RX",
        "TIM1_CH3",
        "UART1_TX",
        "I2C_SDA",
        "TIM1_CH1",
        "SPI2_SCK",
        "I2S2_CK",
        "CAN_TX"
      ],
      "additional_functions": [],
      "packages": {
        "LQFP48": 31,
        "LQFP32": 20,
        "QFN325x5 mm2": 20,
        "QFN324x4 mm2": 20,
        "TSSOP20": 18
      },
      "alternate_functions": {
        "AF0": "TIM17_BKIN",
        "AF1": "UART1_RX",
        "AF2": "TIM1_CH3",
        "AF3": "UART1_TX",
        "AF4": "I2C_SDA",
        "AF5": null,
        "AF6": "TIM1_CH1",
        "AF7": "SPI2_SCK/I2S2_CK",
        "AF8": "CAN_TX"
      }
    },
    {
      "name": "PA11",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PA11",
      "multiplex_functions": [
        "UART3_TX",
        "UART1_CTS",
        "TIM1_CH4",
        "CAN_RX",
        "SPI2_MOSI",
        "I2S2_SD",
        "I2C_SCL",
        "COMP1_OUT"
      ],
      "additional_functions": [],
      "packages": {
        "LQFP48": 32,
        "LQFP32": 21,
        "QFN325x5 mm2": 21,
        "QFN324x4 mm2": 21,
        "TSSOP20": null
      },
      "alternate_functions": {
        "AF0": "UART3_TX",
        "AF1": "UART1_CTS",
        "AF2": "TIM1_CH4",
        "AF3": "CAN_RX",
        "AF4": "SPI2_MOSI/I2S2_SD",
        "AF5": "I2C_SCL",
        "AF6": null,
        "AF7": "COMP1_OUT",
        "AF8": null
      }
    },
    {
      "name": "PA12",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PA12",
      "multiplex_functions": [
        "UART3_RX",
        "UART1_RTS",
        "TIM1_ETR",
        "CAN_TX",
        "SPI2_MISO",
        "I2S2_MCK",
        "I2C_SDA",
        "TIM1_CH2"
      ],
      "additional_functions": [],
      "packages": {
        "LQFP48": 33,
        "LQFP32": 22,
        "QFN325x5 mm2": 22,
        "QFN324x4 mm2": 22,
        "TSSOP20": null
      },
      "alternate_functions": {
        "AF0": "UART3_RX",
        "AF1": "UART1_RTS",
        "AF2": "TIM1_ETR",
        "AF3": "CAN_TX",
        "AF4": "SPI2_MISO/I2S2_MCK",
        "AF5": "I2C_SDA",
        "AF6": null,
        "AF7": "TIM1_CH2",
        "AF8": null
      }
    },
    {
      "name": "PA13",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PA13",
      "multiplex_functions": [
        "SWDIO",
        "UART1_TX",
        "SPI2_MISO",
        "I2S2_MCK",
        "MCO",
        "TIM1_CH2",
        "TIM1_BKIN"
      ],
      "additional_functions": [],
      "packages": {
        "LQFP48": 34,
        "LQFP32": 23,
        "QFN325x5 mm2": 23,
        "QFN324x4 mm2": 23,
        "TSSOP20": 19
      },
      "alternate_functions": {
        "AF0": "SWDIO",
        "AF1": null,
        "AF2": "UART1_TX",
        "AF3": null,
        "AF4": "SPI2_MISO/I2S2_MCK",
        "AF5": "MCO",
        "AF6": "TIM1_CH2",
        "AF7": "TIM1_BKIN",
        "AF8": null
      }
    },
    {
      "name": "PD2",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PD2",
      "multiplex_functions": [],
      "additional_functions": [],
      "packages": {
        "LQFP48": 35,
        "LQFP32": null,
        "QFN325x5 mm2": null,
        "QFN324x4 mm2": null,
        "TSSOP20": null
      },
      "alternate_functions": {
        "AF0": null,
        "AF1": null,
        "AF2": null,
        "AF3": null,
        "AF4": null,
        "AF5": null,
        "AF6": null,
        "AF7": null,
        "AF8": null
      }
    },
    {
      "name": "PD3",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PD3",
      "multiplex_functions": [],
      "additional_functions": [],
      "packages": {
        "LQFP48": 36,
        "LQFP32": null,
        "QFN325x5 mm2": null,
        "QFN324x4 mm2": null,
        "TSSOP20": null
      },
      "alternate_functions": {
        "AF0": null,
        "AF1": null,
        "AF2": null,
        "AF3": null,
        "AF4": null,
        "AF5": null,
        "AF6": null,
        "AF7": null,
        "AF8": null
      }
    },
    {
      "name": "PA14",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PA14",
      "multiplex_functions": [
        "SWDCLK",
        "UART2_TX",
        "UART1_RX",
        "SPI1_NSS",
        "I2S1_WS"
      ],
      "additional_functions": [],
      "packages": {
        "LQFP48": 37,
        "LQFP32": 24,
        "QFN325x5 mm2": 24,
        "QFN324x4 mm2": 24,
        "TSSOP20": 20
      },
      "alternate_functions": {
        "AF0": "SWDCLK",
        "AF1": "UART2_TX",
        "AF2": "UART1_RX",
        "AF3": "SPI1_NSS/I2S1_WS",
        "AF4": null,
        "AF5": null,
        "AF6": null,
        "AF7": null,
        "AF8": null
      }
    },
    {
      "name": "PA15",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PA15",
      "multiplex_functions": [
        "SPI1_NSS",
        "I2S1_WS",
        "UART2_RX",
        "TIM2_CH1",
        "TIM2_ETR"
      ],
      "additional_functions": [],
      "packages": {
        "LQFP48": 38,
        "LQFP32": 25,
        "QFN325x5 mm2": 25,
        "QFN324x4 mm2": 25,
        "TSSOP20": null
      },
      "alternate_functions": {
        "AF0": "SPI1_NSS/I2S1_WS",
        "AF1": "UART2_RX",
        "AF2": "TIM2_CH1/TIM2_ETR",
        "AF3": null,
        "AF4": null,
        "AF5": null,
        "AF6": null,
        "AF7": null,
        "AF8": null
      }
    },
    {
      "name": "PB3",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PB3",
      "multiplex_functions": [
        "SPI1_SCK",
        "I2S1_CK",
        "TIM2_CH2",
        "UART1_TX",
        "TIM2_CH3",
        "TIM1_CH1",
        "TIM2_CH1"
      ],
      "additional_functions": [
        "ADC1_VIN[10]"
      ],
      "packages": {
        "LQFP48": 39,
        "LQFP32": 26,
        "QFN325x5 mm2": 26,
        "QFN324x4 mm2": 26,
        "TSSOP20": null
      },
      "alternate_functions": {
        "AF0": "SPI1_SCK/I2S1_CK",
        "AF1": null,
        "AF2": "TIM2_CH2",
        "AF3": "UART1_TX",
        "AF4": "TIM2_CH3",
        "AF5": null,
        "AF6": "TIM1_CH1",
        "AF7": "TIM2_CH1",
        "AF8": null
      }
    },
    {
      "name": "PB4",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PB4",
      "multiplex_functions": [
        "SPI1_MISO",
        "I2S1_MCK",
        "TIM3_CH1",
        "UART1_RX",
        "TIM17_BKIN",
        "TIM1_CH2",
        "TIM2_CH2"
      ],
      "additional_functions": [
        "ADC1_VIN[11]"
      ],
      "packages": {
        "LQFP48": 40,
        "LQFP32": 27,
        "QFN325x5 mm2": 27,
        "QFN324x4 mm2": 27,
        "TSSOP20": null
      },
      "alternate_functions": {
        "AF0": "SPI1_MISO/I2S1_MCK",
        "AF1": "TIM3_CH1",
        "AF2": null,
        "AF3": "UART1_RX",
        "AF4": null,
        "AF5": "TIM17_BKIN",
        "AF6": "TIM1_CH2",
        "AF7": "TIM2_CH2",
        "AF8": null
      }
    },
    {
      "name": "PB5",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PB5",
      "multiplex_functions": [
        "SPI1_MOSI",
        "I2S1_SD",
        "TIM3_CH2",
        "TIM16_BKIN",
        "MCO",
        "TIM1_CH3",
        "TIM2_CH3"
      ],
      "additional_functions": [],
      "packages": {
        "LQFP48": 41,
        "LQFP32": 28,
        "QFN325x5 mm2": 28,
        "QFN324x4 mm2": 28,
        "TSSOP20": null
      },
      "alternate_functions": {
        "AF0": "SPI1_MOSI/I2S1_SD",
        "AF1": "TIM3_CH2",
        "AF2": "TIM16_BKIN",
        "AF3": "MCO",
        "AF4": null,
        "AF5": null,
        "AF6": "TIM1_CH3",
        "AF7": "TIM2_CH3",
        "AF8": null
      }
    },
    {
      "name": "PB6",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PB6",
      "multiplex_functions": [
        "UART1_TX",
        "I2C_SCL",
        "TIM16_CH1N",
        "TIM2_CH1"
      ],
      "additional_functions": [],
      "packages": {
        "LQFP48": 42,
        "LQFP32": 29,
        "QFN325x5 mm2": 29,
        "QFN324x4 mm2": 29,
        "TSSOP20": null
      },
      "alternate_functions": {
        "AF0": "UART1_TX",
        "AF1": "I2C_SCL",
        "AF2": "TIM16_CH1N",
        "AF3": null,
        "AF4": "TIM2_CH1",
        "AF5": null,
        "AF6": null,
        "AF7": null,
        "AF8": null
      }
    },
    {
      "name": "PB7",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PB7",
      "multiplex_functions": [
        "UART1_RX",
        "I2C_SDA",
        "TIM17_CH1N",
        "UART2_TX"
      ],
      "additional_functions": [
        "ADC1_VIN[12]"
      ],
      "packages": {
        "LQFP48": 43,
        "LQFP32": 30,
        "QFN325x5 mm2": 30,
        "QFN324x4 mm2": 30,
        "TSSOP20": null
      },
      "alternate_functions": {
        "AF0": "UART1_RX",
        "AF1": "I2C_SDA",
        "AF2": "TIM17_CH1N",
        "AF3": null,
        "AF4": "UART2_TX",
        "AF5": null,
        "AF6": null,
        "AF7": null,
        "AF8": null
      }
    },
    {
      "name": "PD5 BOOT0",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PD5",
      "multiplex_functions": [],
      "additional_functions": [],
      "packages": {
        "LQFP48": 44,
        "LQFP32": 31,
        "QFN325x5 mm2": 31,
        "QFN324x4 mm2": null,
        "TSSOP20": 1
      },
      "alternate_functions": {
        "AF0": null,
        "AF1": null,
        "AF2": null,
        "AF3": null,
        "AF4": null,
        "AF5": null,
        "AF6": null,
        "AF7": null,
        "AF8": null
      }
    },
    {
      "name": "PB8",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PB8",
      "multiplex_functions": [
        "I2C_SCL",
        "TIM16_CH1",
        "CAN_RX",
        "UART2_RX"
      ],
      "additional_functions": [],
      "packages": {
        "LQFP48": 45,
        "LQFP32": null,
        "QFN325x5 mm2": 32,
        "QFN324x4 mm2": 31,
        "TSSOP20": null
      },
      "alternate_functions": {
        "AF0": null,
        "AF1": "I2C_SCL",
        "AF2": "TIM16_CH1",
        "AF3": "CAN_RX",
        "AF4": "UART2_RX",
        "AF5": null,
        "AF6": null,
        "AF7": null,
        "AF8": null
      }
    },
    {
      "name": "PB9",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PB9",
      "multiplex_functions": [
        "I2C_SDA",
        "TIM17_CH1",
        "CAN_TX",
        "TIM1_CH4",
        "SPI2_NSS",
        "I2S2_WS"
      ],
      "additional_functions": [],
      "packages": {
        "LQFP48": 46,
        "LQFP32": null,
        "QFN325x5 mm2": null,
        "QFN324x4 mm2": null,
        "TSSOP20": null
      },
      "alternate_functions": {
        "AF0": null,
        "AF1": "I2C_SDA",
        "AF2": "TIM17_CH1",
        "AF3": "CAN_TX",
        "AF4": "TIM1_CH4",
        "AF5": "SPI2_NSS/I2S2_WS",
        "AF6": null,
        "AF7": null,
        "AF8": null
      }
    },
    {
      "name": "PD6",
      "type": "I/O",
      "io_level": "TC",
      "main_function": "PD6",
      "multiplex_functions": [
        "SPI1_MISO",
        "I2S1_MCK",
        "TIM3_CH1",
        "TIM1_BKIN",
        "UART2_RX",
        "TIM1_ETR",
        "TIM16_CH1",
        "TIM1_CH3",
        "COMP1_OUT"
      ],
      "additional_functions": [
        "ADC1_VIN[13]",
        "COMP_INM[3]"
      ],
      "packages": {
        "LQFP48": null,
        "LQFP32": null,
        "QFN325x5 mm2": null,
        "QFN324x4 mm2": 32,
        "TSSOP20": null
      },
      "alternate_functions": {
        "AF0": "SPI1_MISO/I2S1_MCK",
        "AF1": "TIM3_CH1",
        "AF2": "TIM1_BKIN",
        "AF3": "UART2_RX",
        "AF4": "TIM1_ETR",
        "AF5": "TIM16_CH1",
        "AF6": "TIM1_CH3",
        "AF7": "COMP1_OUT",
        "AF8": null
      }
    },
    {
      "name": "VSS",
      "type": "S",
      "io_level": "",
      "main_function": "VSS",
      "multiplex_functions": [],
      "additional_functions": [],
      "packages": {
        "LQFP48": 47,
        "LQFP32": 32,
        "QFN325x5 mm2": null,
        "QFN324x4 mm2": null,
        "TSSOP20": null
      },
      "alternate_functions": {}
    },
    {
      "name": "VDD",
      "type": "S",
      "io_level": "",
      "main_function": "VDD",
      "multiplex_functions": [],
      "additional_functions": [],
      "packages": {
        "LQFP48": 48,
        "LQFP32": 1,
        "QFN325x5 mm2": 1,
        "QFN324x4 mm2": 1,
        "TSSOP20": null
      },
      "alternate_functions": {}
    }
  ],
  "metadata": {
    "extraction_date": "2026-07-04T15:45:47.796588",
    "extractor_version": "1.2.0"
  }
}
