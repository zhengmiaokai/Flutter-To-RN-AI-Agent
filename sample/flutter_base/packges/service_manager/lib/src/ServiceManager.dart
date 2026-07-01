abstract class ServiceProtocol {
  void onLoad();
  void onUnLoad();
}

class ServiceManager {
  final hashMap = Map<String, ServiceProtocol>();

  static late final ServiceManager sInstance = ServiceManager();
  static ServiceManager getInstance() => sInstance;

  void setProtocol(String name, ServiceProtocol component) {
    this.hashMap[name] = component;
  }

  ServiceProtocol getProtocol(String name) {
    final component = this.hashMap[name] as ServiceProtocol;
    return component;
  }
}