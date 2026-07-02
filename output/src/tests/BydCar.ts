// Stub class for BydCar used in HomePage
export default class BydCar {
  private version: string;

  constructor(version: string) {
    this.version = version;
  }

  execute(): void {
    console.log(`BydCar v${this.version}: execute`);
  }

  drive(): void {
    console.log(`BydCar v${this.version}: drive`);
  }

  automaticParking(): void {
    console.log(`BydCar v${this.version}: automaticParking`);
  }
}
